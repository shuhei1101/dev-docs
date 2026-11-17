from __future__ import annotations

import io
import json
import os
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _free_port() -> int:
    """OS が払い出して閉じたポートの番号を返却する。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _listening() -> Iterator[int]:
    """テストが `listen` しているポートの番号を指定する。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])


def _stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """標準入力を、指定した文字列に差し替える。"""
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _systemctl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    """`PATH` の先頭に、本文を実行する偽物の `systemctl` を配置し、置いたフォルダを返却する。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "systemctl"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    return bin_dir


def test_main_when_listening(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """つながれば何も出さない（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: True)
    monkeypatch.setattr(hook, "start_server", started.append)
    _stdin(monkeypatch, json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}))
    # 実行
    code = hook.main()
    # 検証
    assert code == 0
    assert capsys.readouterr().out == ""
    assert started == []


def test_main_when_cleared(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """/clear の後も HTTP の要求を送信せず、何も出さない（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    opened: list[Any] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: True)
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: opened.append(args))
    _stdin(monkeypatch, json.dumps({"session_id": "s1", "cwd": "/repo", "source": "clear"}))
    # 実行
    code = hook.main()
    # 検証
    assert code == 0
    assert capsys.readouterr().out == ""
    assert opened == []


def test_main_when_down(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """つながらなければ起動して案内する（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    clone = tmp_path / "clone"
    (clone / ".venv" / "bin").mkdir(parents=True)
    (clone / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    config = tmp_path / "settings.yaml"
    config.write_text(f'version: "1"\nclone: {clone}\n', encoding="utf-8")
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: False)
    monkeypatch.setattr(hook, "start_server", started.append)
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(config))
    monkeypatch.setenv("DEV_DOCS_UNIT", "")
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}),
    )
    # 実行
    code = hook.main()
    # 検証
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert started == [clone]
    assert output["hookSpecificOutput"]["additionalContext"] == hook.RECONNECT_GUIDE


def test_main_when_config_missing(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """端末の設定が無ければ global-setup を案内する（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    config = tmp_path / "missing.yaml"
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: False)
    monkeypatch.setattr(hook, "start_server", started.append)
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(config))
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}),
    )
    # 実行
    code = hook.main()
    # 検証
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert str(config) in context
    assert "/dev-docs:global-setup" in context
    assert started == []


def test_main_when_input_unparsable(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """読み取れない入力では何も出さない（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    _stdin(monkeypatch, "{")
    # 実行
    code = hook.main()
    # 検証
    assert code == 0
    assert capsys.readouterr().out == ""


def test_is_listening(load_hook: Callable[[str], ModuleType]) -> None:
    """待ち受けているポート（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行・検証
    with _listening() as port:
        assert hook.is_listening(port) is True


def test_is_listening_when_closed(load_hook: Callable[[str], ModuleType]) -> None:
    """待ち受けていないポート（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    port = _free_port()
    # 実行
    result = hook.is_listening(port)
    # 検証
    assert result is False


def test_config_path(load_hook: Callable[[str], ModuleType]) -> None:
    """DEV_DOCS_CONFIG が優先（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    env = {"DEV_DOCS_CONFIG": "/tmp/x/settings.yaml", "XDG_CONFIG_HOME": "/tmp/c"}
    # 実行
    result = hook.config_path(env)
    # 検証
    assert result == Path("/tmp/x/settings.yaml")


def test_config_path_when_xdg_config_home_set(load_hook: Callable[[str], ModuleType]) -> None:
    """XDG_CONFIG_HOME の下（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    env = {"XDG_CONFIG_HOME": "/tmp/c"}
    # 実行
    result = hook.config_path(env)
    # 検証
    assert result == Path("/tmp/c/dev-docs/settings.yaml")


@pytest.mark.parametrize("env", [{}, {"XDG_CONFIG_HOME": ""}, {"XDG_CONFIG_HOME": "rel"}])
def test_config_path_when_unset_or_relative(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
) -> None:
    """未設定・空の文字列・相対パスは既定（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    monkeypatch.setenv("HOME", "/home/u")
    # 実行
    result = hook.config_path(env)
    # 検証
    assert result == Path("/home/u/.config/dev-docs/settings.yaml")


def test_read_clone(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """引用符と ~ を扱う（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    config = tmp_path / "settings.yaml"
    config.write_text(
        'version: "1"\nclone: "~/dev-docs"  # クローン\nsources:\n  - id: a\n    clone: /other\n',
        encoding="utf-8",
    )
    # 実行
    result = hook.read_clone(config)
    # 検証
    assert result == Path.home() / "dev-docs"


def test_read_clone_when_missing(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """行かファイルが無い（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    no_line = tmp_path / "no_line.yaml"
    no_line.write_text('version: "1"\n', encoding="utf-8")
    # 実行
    result_no_line = hook.read_clone(no_line)
    result_no_file = hook.read_clone(tmp_path / "missing.yaml")
    # 検証
    assert result_no_line is None
    assert result_no_file is None


@pytest.mark.filterwarnings("ignore:subprocess .* is still running:ResourceWarning")
def test_start_server(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """切り離して起動する（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    clone = tmp_path / "clone"
    python = clone / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    record = tmp_path / "args.txt"
    python.write_text(f'#!/bin/sh\necho "$@" > "{record}"\n', encoding="utf-8")
    python.chmod(0o755)
    # 実行
    hook.start_server(clone)
    # 検証
    deadline = time.monotonic() + 5
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert record.read_text(encoding="utf-8").strip() == "-m dev_docs serve"


def test_start_server_when_no_venv(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """.venv が無い（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行・検証
    with pytest.raises(FileNotFoundError):
        hook.start_server(tmp_path)


def _down_unit_hook(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, list[Path]]:
    """ポートにつながらず、`DEV_DOCS_UNIT` が `x.service` のフックと、サーバーの起動の記録を返却する。"""
    hook = load_hook("session_start")
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: False)
    monkeypatch.setattr(hook, "start_server", started.append)
    monkeypatch.setenv("DEV_DOCS_UNIT", "x.service")
    _stdin(monkeypatch, json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}))
    return hook, started


def test_main_when_unit_exists(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """unit があれば unit を起動する（正常系）。"""
    # 準備
    hook, started = _down_unit_hook(load_hook, monkeypatch)
    units: list[str] = []
    monkeypatch.setattr(hook, "unit_exists", lambda unit: True)
    monkeypatch.setattr(hook, "start_unit", units.append)
    # 実行
    code = hook.main()
    # 検証
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert units == ["x.service"]
    assert output["hookSpecificOutput"]["additionalContext"] == hook.RECONNECT_GUIDE
    assert started == []


def test_main_when_unit_start_fails(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """unit を起動できなければ理由を案内し、切り離しては起動しない（異常系）。"""
    # 準備
    hook, started = _down_unit_hook(load_hook, monkeypatch)

    def fail(unit: str) -> None:
        raise hook.UnitStartError("Failed to start")

    monkeypatch.setattr(hook, "unit_exists", lambda unit: True)
    monkeypatch.setattr(hook, "start_unit", fail)
    # 実行
    code = hook.main()
    # 検証
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert "x.service" in context
    assert "Failed to start" in context
    assert started == []


def test_main_when_unit_check_times_out(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """unit の有無が打ち切られたら理由を案内し、どちらの起動もしない（異常系）。"""
    # 準備
    hook, started = _down_unit_hook(load_hook, monkeypatch)
    units: list[str] = []

    def timeout(unit: str) -> bool:
        raise hook.UnitStartError("systemctl --user cat が 0.1 秒で終わらなかった")

    monkeypatch.setattr(hook, "unit_exists", timeout)
    monkeypatch.setattr(hook, "start_unit", units.append)
    # 実行
    code = hook.main()
    # 検証
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert "x.service" in context
    assert units == []
    assert started == []


def test_unit_name(load_hook: Callable[[str], ModuleType]) -> None:
    """既定と指定（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行
    default = hook.unit_name({})
    given = hook.unit_name({"DEV_DOCS_UNIT": "x.service"})
    # 検証
    assert default == "dev-docs.service"
    assert given == "x.service"


def test_unit_name_when_empty(load_hook: Callable[[str], ModuleType]) -> None:
    """空の文字列は unit を使用しない（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行
    result = hook.unit_name({"DEV_DOCS_UNIT": ""})
    # 検証
    assert result is None


def test_unit_exists(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """終了コードで unit の有無を分ける（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    _systemctl(tmp_path, monkeypatch, '[ "$3" = "ok.service" ] && exit 0\nexit 1')
    # 実行
    found = hook.unit_exists("ok.service")
    missing = hook.unit_exists("ng.service")
    # 検証
    assert found is True
    assert missing is False


def test_unit_exists_when_no_systemctl(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """systemctl が無い（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    # 実行
    result = hook.unit_exists("dev-docs.service")
    # 検証
    assert result is False


def test_unit_exists_when_timeout(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """systemctl が打ち切られる（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    _systemctl(tmp_path, monkeypatch, "sleep 1")
    # 実行・検証
    with pytest.raises(hook.UnitStartError, match="systemctl --user cat"):
        hook.unit_exists("dev-docs.service")


def test_start_unit(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """unit の起動を依頼する（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    record = tmp_path / "args.txt"
    _systemctl(tmp_path, monkeypatch, f'echo "$@" > "{record}"')
    # 実行
    hook.start_unit("x.service")
    # 検証
    assert record.read_text(encoding="utf-8").strip() == "--user start --no-block x.service"


def test_start_unit_when_failed(
    load_hook: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """unit の起動に失敗する（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    _systemctl(tmp_path, monkeypatch, 'echo "Failed to start x.service" >&2\nexit 1')
    # 実行・検証
    with pytest.raises(hook.UnitStartError, match="Failed to start"):
        hook.start_unit("x.service")
