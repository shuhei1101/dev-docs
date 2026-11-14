from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import socket
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn

from dev_docs import main as main_module
from dev_docs.features.settings.types import TerminalConfig
from dev_docs.integrations.project_index.client import PROJECT_INDEX_TIMEOUT_SEC
from dev_docs.main import (
    PortInUseError,
    announce_sources,
    build_handlers,
    check_port,
    run_migrate,
    run_serve,
)
from dev_docs.shared.yaml_io import load_yaml

from .conftest import FakeIndex

SETTINGS_V1 = 'version: "1"\nclone: /x\nlog_dir: /logs\n'
SOURCES_V1 = (
    'version: "1"\nclone: /x\nsources:\n'
    "  - id: sample\n    config: /s/dev-docs.yaml\n"
    "  - id: notes\n    config: /n/dev-docs.yaml\n"
)


def _free_port() -> int:
    """OS が払い出して閉じたポートの番号を返却する。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _closed_address() -> str:
    """何も待ち受けていない project-index のアドレスを返却する。"""
    return f"http://127.0.0.1:{_free_port()}"


@contextmanager
def _listening() -> Iterator[int]:
    """テストが `listen` しているポートの番号を指定する。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])


@contextmanager
def _http_index(fake: FakeIndex) -> Iterator[str]:
    """`FakeIndex` に応答させる偽物の project-index の HTTP サーバーを起動し、アドレスを指定する。"""

    class Handler(BaseHTTPRequestHandler):
        def _answer(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            request = httpx.Request(
                self.command,
                f"http://127.0.0.1{self.path}",
                headers=dict(self.headers),
                content=self.rfile.read(length),
            )
            response = fake.handle(request)
            body = response.content
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = _answer

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _serving_index() -> FakeIndex:
    """sample・notes を配信中、broken を配信していないと返却する偽物を作る。"""
    return FakeIndex(
        sources=[
            {"id": "sample", "status": "serving", "errors": []},
            {"id": "notes", "status": "serving", "errors": []},
            {"id": "broken", "status": "not_served", "errors": []},
        ]
    )


def _write_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> Path:
    """端末の設定を書き込んで `DEV_DOCS_CONFIG` に指定し、そのパスを返却する。"""
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(path))
    return path


def _serve_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, address: str, extra: str = ""
) -> Path:
    """`project_index` を持つ端末の設定を `DEV_DOCS_CONFIG` に指定し、そのパスを返却する。"""
    text = (
        f'version: "2"\nclone: {tmp_path}\nstate_dir: {tmp_path / "state"}\n'
        f"project_index: {address}\n{extra}"
    )
    return _write_settings(tmp_path, monkeypatch, text)


def _record_config(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`uvicorn.Config` に指定した引数を記録する。"""
    configs: list[dict[str, Any]] = []
    real_config = uvicorn.Config

    def recording_config(*args: Any, **kwargs: Any) -> uvicorn.Config:
        configs.append(kwargs)
        return real_config(*args, **kwargs)

    monkeypatch.setattr(uvicorn, "Config", recording_config)
    return configs


def _record_announce(monkeypatch: pytest.MonkeyPatch) -> list[threading.Thread]:
    """配信元の通知のスレッドを記録する。"""
    threads: list[threading.Thread] = []
    real_announce = main_module.announce_sources

    def recording_announce(terminal: TerminalConfig) -> threading.Thread:
        thread = real_announce(terminal)
        threads.append(thread)
        return thread

    monkeypatch.setattr(main_module, "announce_sources", recording_announce)
    return threads


def _started(self: uvicorn.Server, *args: Any, **kwargs: Any) -> None:
    """待ち受けを始めたことにして戻る `uvicorn.Server.run` の偽物。"""
    self.started = True


def test_run_serve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """待ち受けて配信元を出す（正常系）。"""
    # 準備
    port = _free_port()
    monkeypatch.setenv("DEV_DOCS_PORT", str(port))
    configs = _record_config(monkeypatch)
    threads = _record_announce(monkeypatch)
    monkeypatch.setattr(uvicorn.Server, "run", _started)
    with _http_index(_serving_index()) as address:
        _serve_settings(tmp_path, monkeypatch, address)
        # 実行
        code = run_serve(argparse.Namespace())
        threads[0].join(timeout=30)
    # 検証
    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines.index(f"http://127.0.0.1:{port}/") < lines.index("sample")
    assert configs[0]["host"] == "127.0.0.1"


def test_run_serve_when_config_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """端末の設定が違反する（異常系）。"""
    # 準備
    _write_settings(
        tmp_path,
        monkeypatch,
        'version: "2"\nclone: /tmp/clone\nport: abc\nproject_index: 127.0.0.1:8786\n',
    )
    # 実行
    code = run_serve(argparse.Namespace())
    # 検証
    error = capsys.readouterr().err
    assert code == 2
    assert "project_index" in error
    assert "port" in error


def test_run_serve_when_port_in_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ポートが使用中（異常系）。"""
    # 準備
    _serve_settings(tmp_path, monkeypatch, _closed_address())
    # 実行
    with _listening() as port:
        monkeypatch.setenv("DEV_DOCS_PORT", str(port))
        code = run_serve(argparse.Namespace())
    # 検証
    error = capsys.readouterr().err
    assert code == 3
    assert str(port) in error
    assert "DEV_DOCS_PORT" in error


def test_run_serve_when_prompt_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """プロンプトの YAML が違反する（異常系）。"""
    from dev_docs.features.prompt_doc.runtime import DEFAULT_PROMPTS_DIR

    # 準備
    _serve_settings(tmp_path, monkeypatch, _closed_address())
    prompts = tmp_path / "prompts"
    shutil.copytree(DEFAULT_PROMPTS_DIR, prompts)
    broken = prompts / "mcp/admin/tools/status.yaml"
    value = load_yaml(broken.read_text(encoding="utf-8"))
    del value["kind"]
    broken.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_PROMPTS_DIR", str(prompts))
    monkeypatch.setenv("DEV_DOCS_PORT", str(_free_port()))
    runs: list[uvicorn.Server] = []

    def fake_run(self: uvicorn.Server, *args: Any, **kwargs: Any) -> None:
        runs.append(self)

    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    # 実行
    code = run_serve(argparse.Namespace())
    # 検証
    error = capsys.readouterr().err
    assert code == 4
    assert str(broken) in error
    assert "kind" in error
    assert runs == []


def test_run_serve_when_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """再起動の要求で同じプロセスを置き換える（正常系）。"""
    # 準備
    _serve_settings(tmp_path, monkeypatch, _closed_address())
    monkeypatch.setenv("DEV_DOCS_PORT", str(_free_port()))
    captured: dict[str, Any] = {}
    real_build_handlers = main_module.build_handlers

    def spy_build_handlers(terminal: TerminalConfig) -> Any:
        captured["handlers"] = real_build_handlers(terminal)
        return captured["handlers"]

    configs = _record_config(monkeypatch)

    def fake_run(self: uvicorn.Server, *args: Any, **kwargs: Any) -> None:
        self.started = True
        captured["handlers"].restart.request()

    executed: list[tuple[str, list[str]]] = []

    def fake_execv(path: str, argv: list[str]) -> None:
        executed.append((path, argv))

    monkeypatch.setattr(main_module, "build_handlers", spy_build_handlers)
    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    monkeypatch.setattr(os, "execv", fake_execv)
    # 実行
    run_serve(argparse.Namespace())
    # 検証
    assert executed == [(sys.executable, [sys.executable, "-m", "dev_docs", "serve"])]
    assert configs[0]["timeout_graceful_shutdown"] == int(PROJECT_INDEX_TIMEOUT_SEC * 1.5)


def test_run_serve_when_leftover_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """端末の設定に残った sources を警告する（正常系）。"""
    # 準備
    _serve_settings(
        tmp_path,
        monkeypatch,
        _closed_address(),
        "sources:\n  - id: sample\n    config: /s/project-index.yaml\n",
    )
    monkeypatch.setenv("DEV_DOCS_PORT", str(_free_port()))
    threads = _record_announce(monkeypatch)
    monkeypatch.setattr(uvicorn.Server, "run", _started)
    # 実行
    with caplog.at_level(logging.WARNING, logger="dev_docs.main"):
        code = run_serve(argparse.Namespace())
        threads[0].join(timeout=30)
    # 検証
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "sources" in record.getMessage()
    ]
    assert code == 0
    assert len(warnings) == 1
    assert "sample" in warnings[0]
    assert "project-index" in warnings[0]


def test_check_port() -> None:
    """空いているポート（正常系）。"""
    # 準備
    port = _free_port()
    # 実行・検証
    check_port("127.0.0.1", port)


def test_check_port_when_time_wait() -> None:
    """閉じたばかりの接続が残るポート（正常系）。"""
    # 準備
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = int(server.getsockname()[1])
        with closing(socket.create_connection(("127.0.0.1", port))):
            connection, _ = server.accept()
            # サーバー側から先に閉じて、サーバー側のポートに TIME_WAIT を残す
            connection.close()
    # 実行・検証
    check_port("127.0.0.1", port)


def test_check_port_when_in_use() -> None:
    """使用中のポート（異常系）。"""
    # 準備・実行・検証
    with _listening() as port, pytest.raises(PortInUseError) as exc_info:
        check_port("127.0.0.1", port)
    assert exc_info.value.port == port


def test_build_handlers(
    tmp_path: Path, make_terminal_config: Callable[..., TerminalConfig]
) -> None:
    """部品を作り project-index には問い合わせない（正常系）。"""
    # 準備
    address = _closed_address()
    state_dir = tmp_path / "new-state"
    terminal = make_terminal_config(state_dir=state_dir, project_index=address)
    # 実行
    handlers = build_handlers(terminal)
    # 検証
    assert state_dir.is_dir()
    assert handlers.project_index.address == address
    assert "mcp/admin/tools/status" in handlers.prompts.prompts
    assert "mcp/docs/instructions" not in handlers.prompts.prompts


def test_build_handlers_when_prompt_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_terminal_config: Callable[..., TerminalConfig],
) -> None:
    """プロンプトの YAML が違反すると部品を作らない（異常系）。"""
    from dev_docs.features.prompt_doc.types import PromptInvalidError

    # 準備
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    monkeypatch.setenv("DEV_DOCS_PROMPTS_DIR", str(prompts))
    state_dir = tmp_path / "new-state"
    terminal = make_terminal_config(state_dir=state_dir)
    # 実行
    with pytest.raises(PromptInvalidError):
        build_handlers(terminal)
    # 検証
    assert not state_dir.exists()


def test_announce_sources(
    make_terminal_config: Callable[..., TerminalConfig], capsys: pytest.CaptureFixture[str]
) -> None:
    """配信中の配信元を出す（正常系）。"""
    # 準備
    with _http_index(_serving_index()) as address:
        terminal = make_terminal_config(project_index=address)
        # 実行
        announce_sources(terminal).join(timeout=30)
    # 検証
    assert capsys.readouterr().out.splitlines() == ["sample", "notes"]


def test_announce_sources_when_unreachable(
    make_terminal_config: Callable[..., TerminalConfig],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """project-index につながらない（正常系）。"""
    # 準備
    address = _closed_address()
    terminal = make_terminal_config(project_index=address)
    # 実行
    with caplog.at_level(logging.ERROR, logger="dev_docs.main"):
        announce_sources(terminal).join(timeout=30)
    # 検証
    error = capsys.readouterr().err
    assert address in error
    assert "project-index を起動してから" in error
    assert len([record for record in caplog.records if record.levelno == logging.ERROR]) == 1


def _migrate_args(**overrides: Any) -> argparse.Namespace:
    """`migrate` の解析結果を作る。"""
    values: dict[str, Any] = {
        "plan": False,
        "record": False,
        "allow_destructive": False,
        "project_index": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_run_migrate_when_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write_steps: Callable[..., None],
) -> None:
    """適用する手順を表示するだけで書き換えない（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SETTINGS_V1)
    write_steps(
        "settings",
        "2",
        [
            {"op": "rename", "path": "log_dir", "to": "state_dir", "description": "改名"},
            {"op": "delete", "path": "legacy", "description": "削除"},
        ],
    )
    # 実行
    code = run_migrate(_migrate_args(plan=True))
    # 検証
    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["2: 改名", "2: 削除 [destructive]"]
    assert settings.read_text(encoding="utf-8") == SETTINGS_V1


def test_run_migrate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write_steps: Callable[..., None],
) -> None:
    """手順を適用してバックアップを取る（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SETTINGS_V1)
    write_steps(
        "settings",
        "2",
        [{"op": "rename", "path": "log_dir", "to": "state_dir", "description": "改名"}],
    )
    # 実行
    code = run_migrate(_migrate_args())
    # 検証
    assert code == 0
    assert load_yaml(settings.read_text(encoding="utf-8")) == {
        "version": "2",
        "clone": "/x",
        "state_dir": "/logs",
    }
    assert "settings.yaml.bak-" in capsys.readouterr().out


def test_run_migrate_when_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """同じバージョンなら何もしない（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, 'version: "2"\nclone: /x\n')
    # 実行
    code = run_migrate(_migrate_args())
    # 検証
    assert code == 0
    assert "移し替えは要りません" in capsys.readouterr().out
    assert list(settings.parent.glob("*.bak-*")) == []


def test_run_migrate_when_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_steps: Callable[..., None]
) -> None:
    """`--record` は version だけを書き換える（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SETTINGS_V1)
    write_steps(
        "settings",
        "2",
        [{"op": "rename", "path": "log_dir", "to": "state_dir", "description": "改名"}],
    )
    # 実行
    code = run_migrate(_migrate_args(record=True))
    # 検証
    assert code == 0
    assert load_yaml(settings.read_text(encoding="utf-8")) == {
        "version": "2",
        "clone": "/x",
        "log_dir": "/logs",
    }


def test_run_migrate_when_destructive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write_steps: Callable[..., None],
) -> None:
    """破壊的な手順で止める（異常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SETTINGS_V1)
    write_steps("settings", "2", [{"op": "delete", "path": "log_dir", "description": "削除"}])
    # 実行
    code = run_migrate(_migrate_args())
    # 検証
    assert code == 5
    assert "--allow-destructive" in capsys.readouterr().err
    assert settings.read_text(encoding="utf-8") == SETTINGS_V1


def test_run_migrate_when_newer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """新しすぎる設定を書き換えない（異常系）。"""
    # 準備
    text = 'version: "9"\nclone: /x\n'
    settings = _write_settings(tmp_path, monkeypatch, text)
    # 実行
    code = run_migrate(_migrate_args())
    # 検証
    assert code == 6
    assert "dev-docs を更新してください" in capsys.readouterr().err
    assert settings.read_text(encoding="utf-8") == text


def test_run_migrate_when_config_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """対象が無い（異常系）。"""
    # 準備
    missing = tmp_path / "missing" / "settings.yaml"
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(missing))
    # 実行
    code = run_migrate(_migrate_args())
    # 検証
    assert code == 2
    assert str(missing) in capsys.readouterr().err


def test_run_migrate_when_sources_moved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write_steps: Callable[..., None],
) -> None:
    """sources を project-index へ移す（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SOURCES_V1)
    write_steps(
        "settings",
        "2",
        [{"op": "export_sources", "path": "sources", "description": "移す"}],
    )
    fake = FakeIndex()
    fake.settings = {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            {
                "id": "notes",
                "config": ["/other/dev-docs.yaml"],
                "enabled": True,
                "scope": {"read": [], "write": None},
                "outsideRead": True,
                "status": "serving",
                "errors": [],
                "configVersion": None,
            }
        ],
        "version": "v1",
    }
    with _http_index(fake) as address:
        # 実行
        code = run_migrate(_migrate_args(project_index=address))
    # 検証
    written = load_yaml(settings.read_text(encoding="utf-8"))
    assert code == 0
    assert written["sources"] == [{"id": "notes", "config": "/n/dev-docs.yaml"}]
    assert (written["project_index"], written["version"]) == (address, "2")
    assert "notes" in capsys.readouterr().out
    saves = [request for request in fake.requests if request.method == "PUT"]
    assert len(saves) == 1
    body = json.loads(saves[0].content)
    assert [row["id"] for row in body["sources"]] == ["notes", "sample"]
    assert body["expectedVersion"] == "v1"


def test_run_migrate_when_project_index_unreachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write_steps: Callable[..., None],
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SOURCES_V1)
    write_steps(
        "settings",
        "2",
        [{"op": "export_sources", "path": "sources", "description": "移す"}],
    )
    address = _closed_address()
    # 実行
    code = run_migrate(_migrate_args(project_index=address))
    # 検証
    assert code == 7
    assert settings.read_text(encoding="utf-8") == SOURCES_V1
    assert address in capsys.readouterr().err


def test_run_migrate_when_no_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_steps: Callable[..., None],
) -> None:
    """sources が無ければ project-index へ接続しない（正常系）。"""
    # 準備
    settings = _write_settings(tmp_path, monkeypatch, SETTINGS_V1)
    write_steps(
        "settings",
        "2",
        [{"op": "add", "path": "bind", "value": "127.0.0.1", "description": "追加"}],
    )
    ports: list[str] = []
    monkeypatch.setattr(main_module, "_sources_port", lambda address: ports.append(address))
    # 実行
    code = run_migrate(_migrate_args(project_index=_closed_address()))
    # 検証
    assert code == 0
    assert ports == []
    assert load_yaml(settings.read_text(encoding="utf-8"))["version"] == "2"
