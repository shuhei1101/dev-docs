from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dev_docs.features.settings.query import load_terminal_config
from dev_docs.main import Handlers, build_handlers
from dev_docs.server.app import build_app

LOCAL_BASE_URL = "http://127.0.0.1:8781"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}

SAMPLE_SCHEMA = """\
type: object
title: サンプル
properties:
  id:
    type: string
    title: ID
  name:
    type: string
    title: 名前
  description:
    type: string
    title: 概要
  weight:
    type: integer
    title: 重み
  tags:
    type: array
    title: タグ
    items:
      type: string
  related:
    type: array
    title: 関連
    items:
      type: object
      properties:
        to:
          type: string
        type:
          type: string
      required: [to, type]
  items:
    type: array
    title: 項目
    x-heading: 項目
    items:
      type: object
      properties:
        key:
          type: string
          title: キー
        label:
          type: string
          title: 名称
        notes:
          type: string
          title: 備考
required: [id, name]
"""


@dataclass(frozen=True)
class ToolResult:
    """MCP のツールの呼び出し結果。"""

    is_error: bool
    text: str
    structured: dict[str, Any] | None

    @property
    def data(self) -> Any:
        """本文を JSON として読んだ値を返す。"""
        return json.loads(self.text)


@dataclass
class SourceSpec:
    """端末の設定に並べる配信元 1 つ（フォルダと権限）。"""

    id: str
    folder: Path
    config: list[Path]
    scope_read: list[Path]
    scope_write: list[Path] | None = None
    enabled: bool = True


@dataclass
class ServerEnv:
    """端末の設定から起動したアプリと、呼び出しの道具。"""

    root: Path
    settings_path: Path
    state_dir: Path
    handlers: Handlers
    client: TestClient
    folders: dict[str, Path] = field(default_factory=dict)
    settings_extra: str = ""

    def rewrite_settings(self, *specs: SourceSpec) -> None:
        """起動後に端末の設定の `sources` を手で書き換えたことにする（配信元は読み直さない）。"""
        self.settings_path.write_text(
            _settings_text(self.root, self.state_dir, list(specs), self.settings_extra),
            encoding="utf-8",
        )

    def call(self, name: str, **arguments: Any) -> ToolResult:
        """`/mcp` のツールを HTTP で呼ぶ。"""
        return self._call("/mcp/", name, arguments)

    def call_admin(self, name: str, **arguments: Any) -> ToolResult:
        """`/_admin/mcp` のツールを HTTP で呼ぶ。"""
        return self._call("/_admin/mcp/", name, arguments)

    def tool_names(self) -> list[str]:
        """`/mcp` のツールの名前を並べる。"""
        response = self.client.post(
            "/mcp/",
            headers=MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        return [tool["name"] for tool in response.json()["result"]["tools"]]

    def _call(self, path: str, name: str, arguments: dict[str, Any]) -> ToolResult:
        """JSON-RPC の `tools/call` を送って結果を読む。"""
        response = self.client.post(
            path,
            headers=MCP_HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        result = response.json()["result"]
        return ToolResult(
            is_error=bool(result.get("isError")),
            text="".join(part["text"] for part in result["content"] if part["type"] == "text"),
            structured=result.get("structuredContent"),
        )


def sample_config(
    extra: str = "", *, name: str = "sample", description: str = "", version: str = ""
) -> str:
    """文書の種類 `sample` を 1 つ持つ配信元の設定の YAML を作る。"""
    description_line = f"description: {description}\n" if description else ""
    version_line = f'version: "{version}"\n' if version else ""
    return (
        f"{version_line}"
        f"name: {name}\n"
        f"{description_line}"
        "default_ref: develop\n"
        "documents:\n"
        "  - id: sample\n"
        "    paths: [docs/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
        f"{extra}"
    )


def sample_doc(doc_id: str, name: str, **fields: Any) -> str:
    """`sample` の種類の文書の YAML を作る。"""
    lines = [f"id: {doc_id}", f"name: {name}"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def sample_files(**overrides: str) -> dict[str, str]:
    """文書 2 件（doc-1・doc-2）と設定・スキーマの、配信元のファイル一式を返す。"""
    files = {
        "dev-docs.yaml": sample_config(),
        "schemas/sample.schema.yaml": SAMPLE_SCHEMA,
        "docs/doc-1.yaml": sample_doc("doc-1", "文書 1", description="1 件目", tags=["a"]),
        "docs/doc-2.yaml": sample_doc("doc-2", "文書 2", description="2 件目", tags=["a", "b"]),
    }
    files.update(overrides)
    return files


# `/dev-docs:setup` が配信元にコピーする管理用の YAML のスキーマ
FILES_SCHEMA_TEMPLATE = Path(__file__).parents[3] / "templates" / "files.schema.yaml"

FILES_ROW = (
    "  - id: src\n"
    "    paths: [src/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)


def sample_sync_files(unindexed: int = 1, *, version: str = "3") -> dict[str, str]:
    """管理用の YAML に無いファイルを `unindexed` 件持つ、配信元のファイル一式を返す。"""
    files = sample_files(**{"dev-docs.yaml": sample_config(FILES_ROW, version=version)})
    files["schemas/files.schema.yaml"] = FILES_SCHEMA_TEMPLATE.read_text(encoding="utf-8")
    files["src/files.yaml"] = "files:\n  - path: a.py\n"
    files["src/a.py"] = "a = 1\n"
    files.update({f"src/extra{index}.py": "x = 1\n" for index in range(unindexed)})
    return files


@pytest.fixture
def sample_sync_file_set() -> Callable[..., dict[str, str]]:
    """管理用の YAML に無いファイルを持つ配信元のファイル一式を作る関数を返す。"""
    return sample_sync_files


@pytest.fixture
def sample_config_text() -> Callable[..., str]:
    """配信元の設定の YAML を作る関数を返す。"""
    return sample_config


@pytest.fixture
def sample_doc_text() -> Callable[..., str]:
    """`sample` の種類の文書の YAML を作る関数を返す。"""
    return sample_doc


@pytest.fixture
def sample_file_set() -> Callable[..., dict[str, str]]:
    """配信元のファイル一式を作る関数を返す。"""
    return sample_files


@pytest.fixture
def make_source(
    tmp_path: Path,
    git_repo: Callable[..., Path],
    write_files: Callable[[Path, dict[str, str]], None],
) -> Callable[..., SourceSpec]:
    """配信元のフォルダ（git リポジトリか Git 管理外）を作って端末の設定に並べる情報を返す関数を返す。"""

    def _make(
        source_id: str,
        files: dict[str, str] | None = None,
        *,
        git: bool = True,
        config_names: tuple[str, ...] = ("dev-docs.yaml",),
        scope_read: list[Path] | None = None,
        scope_write: list[Path] | None = None,
        enabled: bool = True,
        date: str | None = None,
    ) -> SourceSpec:
        content = files if files is not None else sample_files()
        if git:
            folder = git_repo(content, name=source_id, date=date)
        else:
            folder = tmp_path / source_id
            write_files(folder, content)
        return SourceSpec(
            id=source_id,
            folder=folder,
            config=[folder / name for name in config_names],
            scope_read=scope_read if scope_read is not None else [folder],
            scope_write=scope_write,
            enabled=enabled,
        )

    return _make


def _settings_text(root: Path, state_dir: Path, specs: list[SourceSpec], extra: str) -> str:
    """端末の設定の YAML を組み立てる。"""
    lines = [
        'version: "1"',
        f"clone: {root / 'clone'}",
        f"state_dir: {state_dir}",
        extra.rstrip("\n"),
        "sources:" if specs else "sources: []",
    ]
    for spec in specs:
        lines.append(f"  - id: {spec.id}")
        lines.append("    config:")
        lines.extend(f"      - {path}" for path in spec.config)
        if not spec.enabled:
            lines.append("    enabled: false")
        lines.append("    scope:")
        lines.append("      read:")
        lines.extend(f"        - {path}" for path in spec.scope_read)
        if spec.scope_write is not None:
            lines.append("      write:")
            lines.extend(f"        - {path}" for path in spec.scope_write)
    return "\n".join(line for line in lines if line != "") + "\n"


@pytest.fixture
def make_server(tmp_path: Path) -> Iterator[Callable[..., ServerEnv]]:
    """端末の設定を書いてアプリを起動し、HTTP のテストのクライアントを持つ環境を作る関数を返す。"""
    stack = ExitStack()

    def _make(
        *specs: SourceSpec, settings_extra: str = "", screen_dir: Path | None = None
    ) -> ServerEnv:
        state_dir = tmp_path / "state"
        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            _settings_text(tmp_path, state_dir, list(specs), settings_extra), encoding="utf-8"
        )
        handlers = build_handlers(load_terminal_config(settings_path))
        app = (
            build_app(handlers)
            if screen_dir is None
            else build_app(handlers, screen_dir=screen_dir)
        )
        client = stack.enter_context(
            TestClient(app, base_url=LOCAL_BASE_URL, raise_server_exceptions=False)
        )
        return ServerEnv(
            root=tmp_path,
            settings_path=settings_path,
            state_dir=state_dir,
            handlers=handlers,
            client=client,
            folders={spec.id: spec.folder for spec in specs},
            settings_extra=settings_extra,
        )

    with stack:
        yield _make


@pytest.fixture
def add_worktree(run_git: Callable[..., str]) -> Callable[..., Path]:
    """git リポジトリの `.claude/worktrees/{name}` にワークツリーを作り、そのパスを返す関数を返す。"""

    def _add(repo: Path, name: str = "x") -> Path:
        path = repo / ".claude" / "worktrees" / name
        run_git(repo, "worktree", "add", "-b", f"feat/{name}", str(path))
        return path

    return _add


@pytest.fixture
def write_settings(tmp_path: Path) -> Callable[..., Path]:
    """端末の設定の YAML を書いて、そのパスを返す関数を返す。"""

    def _write(*specs: SourceSpec, extra: str = "", name: str = "settings.yaml") -> Path:
        path = tmp_path / name
        path.write_text(
            _settings_text(tmp_path, tmp_path / "state", list(specs), extra), encoding="utf-8"
        )
        return path

    return _write


@pytest.fixture
def free_port() -> Callable[[], int]:
    """今は空いている 127.0.0.1 のポートを返す関数を返す。"""

    def _find() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    return _find


@pytest.fixture
def start_serve() -> Iterator[Callable[..., subprocess.Popen[str]]]:
    """`dev-docs serve` を子プロセスで起動する関数を返す（終了時に止める）。"""
    processes: list[subprocess.Popen[str]] = []

    def _start(settings: Path, port: int) -> subprocess.Popen[str]:
        env = {
            **os.environ,
            "DEV_DOCS_CONFIG": str(settings),
            "DEV_DOCS_PORT": str(port),
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "dev_docs", "serve"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(process)
        return process

    yield _start
    for process in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


@pytest.fixture
def wait_until_serving() -> Callable[..., None]:
    """子プロセスが画面の API で応答するまで待つ関数を返す。"""
    import httpx

    def _wait(process: subprocess.Popen[str], port: int, timeout_sec: float = 30) -> None:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            assert process.poll() is None, "dev-docs serve が先に終わった"
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/_api/openapi.json", timeout=1)
            except httpx.TransportError:
                time.sleep(0.2)
                continue
            if response.status_code == 200:
                return
        message = "dev-docs serve が待ち受けを始めなかった"
        raise AssertionError(message)

    return _wait


@pytest.fixture
def migrations_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """移し替えの手順の置き場所を一時のフォルダに差し替え、そのフォルダを返す。"""
    root = tmp_path / "migrations"
    root.mkdir()
    monkeypatch.setattr("dev_docs.features.migrate.types.MIGRATIONS_DIR", str(root))
    monkeypatch.setattr("dev_docs.features.migrate.steps.MIGRATIONS_DIR", str(root), raising=False)
    return root


@pytest.fixture
def write_steps(migrations_root: Path) -> Callable[..., None]:
    """移し替えの手順のファイル（`{kind}/{バージョン}/steps.yaml`）を書く関数を返す。"""

    def _write(kind: str, version: str, steps: list[dict[str, Any]]) -> None:
        target = migrations_root / kind / version / "steps.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"steps": steps}, ensure_ascii=False), encoding="utf-8")

    return _write


@pytest.fixture
def versions_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev-docs が読める端末の設定と配信元の設定のバージョンを `2` に差し替える。"""
    for name in ("SETTINGS_VERSION", "SOURCE_CONFIG_VERSION"):
        for module in (
            "dev_docs.features.settings.query",
            "dev_docs.features.sources.types",
            "dev_docs.features.sources.service",
            "dev_docs.features.migrate.service",
            "dev_docs.features.admin.service",
            "dev_docs.main",
        ):
            monkeypatch.setattr(f"{module}.{name}", "2", raising=False)


REPO_ROOT = Path(__file__).parents[3]
CLONE_FILES = ("src", "pyproject.toml", "uv.lock", ".python-version")


@dataclass
class DevDocsClone:
    """上流の bare リポジトリと、その dev-docs のクローン（`.venv` つき）。"""

    root: Path
    work: Path
    bare: Path
    clone: Path
    run_git: Callable[..., str]

    def push_upstream(self, files: dict[str, str], message: str = "upstream") -> str:
        """上流の作業ツリーでファイルを書き換えて commit し、bare へ push して commit の SHA を返す。"""
        for name, content in files.items():
            target = self.work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.run_git(self.work, "add", "-A")
        self.run_git(self.work, "commit", "-m", message)
        self.run_git(self.work, "push", str(self.bare), "develop")
        return self.run_git(self.work, "rev-parse", "HEAD").strip()

    def bump_version(self, version: str) -> dict[str, str]:
        """`pyproject.toml` と `uv.lock` の dev-docs のバージョンを書き換えた内容を返す。"""
        pyproject = (self.work / "pyproject.toml").read_text(encoding="utf-8")
        lock = (self.work / "uv.lock").read_text(encoding="utf-8")
        old = next(
            line.split('"')[1] for line in pyproject.splitlines() if line.startswith("version = ")
        )
        return {
            "pyproject.toml": pyproject.replace(f'version = "{old}"', f'version = "{version}"', 1),
            "uv.lock": lock.replace(
                f'name = "dev-docs"\nversion = "{old}"',
                f'name = "dev-docs"\nversion = "{version}"',
                1,
            ),
        }

    def head(self) -> str:
        """クローンの HEAD の SHA を返す。"""
        return self.run_git(self.clone, "rev-parse", "HEAD").strip()


@pytest.fixture
def dev_docs_clone(
    tmp_path: Path, run_git: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> DevDocsClone:
    """dev-docs 自身の小さなコピーを上流にして、`.venv` を作ったクローンを `{tmp}/clone` に作る。"""
    # 依存はキャッシュから入れる（ネットワークを使わない）
    monkeypatch.setenv("UV_OFFLINE", "1")
    work = tmp_path / "work"
    work.mkdir()
    for name in CLONE_FILES:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(source, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, work / name)
    run_git(work, "init", "-b", "develop")
    run_git(work, "add", "-A")
    run_git(work, "commit", "-m", "init")
    bare = tmp_path / "bare.git"
    run_git(tmp_path, "clone", "--bare", str(work), str(bare))
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", str(bare), str(clone))
    subprocess.run(["uv", "sync"], cwd=clone, check=True, capture_output=True)
    return DevDocsClone(tmp_path, work, bare, clone, run_git)


@pytest.fixture
def start_serve_from_clone() -> Iterator[Callable[..., subprocess.Popen[str]]]:
    """クローンの `.venv` の Python で `dev-docs serve` を起動する関数を返す（終了時に止める）。"""
    processes: list[subprocess.Popen[str]] = []

    def _start(clone: Path, settings: Path, port: int) -> subprocess.Popen[str]:
        env = {**os.environ, "DEV_DOCS_CONFIG": str(settings), "DEV_DOCS_PORT": str(port)}
        process = subprocess.Popen(
            [str(clone / ".venv" / "bin" / "python"), "-m", "dev_docs", "serve"],
            env=env,
            cwd=clone,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        processes.append(process)
        return process

    yield _start
    for process in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


STARTED_LINE = "Started server process"
RESTART_WAIT_SEC = 90


@pytest.fixture
def call_tool() -> Callable[..., dict[str, Any]]:
    """起動した子プロセスの MCP のツールを JSON-RPC で呼び、結果の辞書を返す関数を返す。"""
    import httpx

    def _call(
        client: httpx.Client, port: int, endpoint: str, name: str, **arguments: Any
    ) -> dict[str, Any]:
        response = client.post(
            f"http://127.0.0.1:{port}{endpoint}",
            headers=MCP_HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        result: dict[str, Any] = response.json()["result"]
        return result

    return _call


@pytest.fixture
def started_count() -> Callable[[Path], int]:
    """ログに出た「Started server process」の行数を数える関数を返す。"""

    def _count(state_dir: Path) -> int:
        log = state_dir / "logs" / "dev-docs.log"
        return log.read_text(encoding="utf-8").count(STARTED_LINE) if log.exists() else 0

    return _count


@pytest.fixture
def wait_for_restart(started_count: Callable[[Path], int]) -> Callable[..., None]:
    """起動の行が増え、画面の API が応答するまで待つ関数を返す。"""
    import httpx

    def _wait(state_dir: Path, port: int, started: int) -> None:
        deadline = time.monotonic() + RESTART_WAIT_SEC
        while time.monotonic() < deadline:
            if started_count(state_dir) > started:
                try:
                    if httpx.get(
                        f"http://127.0.0.1:{port}/_api/openapi.json", timeout=1
                    ).is_success:
                        return
                except httpx.TransportError:
                    pass
            time.sleep(0.3)
        message = "再起動の後に待ち受けを始めなかった"
        raise AssertionError(message)

    return _wait
