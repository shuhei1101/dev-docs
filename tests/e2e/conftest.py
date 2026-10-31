from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator
from playwright.sync_api import Page, expect, sync_playwright
from ruamel.yaml import YAML

RUN_DIR_ENV = "DEV_DOCS_RUN_DIR"
NOT_RUN = "not_run"
REASON_MAX_CHARS = 2000
SERVE_TIMEOUT_SEC = 30
HTTP_TIMEOUT_SEC = 10
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
LISTEN_STATE = "0A"
TCP_TABLES = ("/proc/net/tcp", "/proc/net/tcp6")
UPDATE_TIMEOUT_SEC = 300
RESTART_WAIT_SEC = 90
START_WAIT_SEC = 60
POLL_INTERVAL_SEC = 0.5

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
required: [id, name]
"""


def pytest_addoption(parser: pytest.Parser) -> None:
    """誤実行を防ぐ `--run-e2e` を足す。"""
    parser.addoption("--run-e2e", action="store_true", default=False, help="E2E テストを実行する")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """`--run-e2e` が無いときは E2E テストを飛ばす。"""
    if config.getoption("run_e2e", default=False):
        return
    skip = pytest.mark.skip(reason="E2E テストは --run-e2e を付けたときだけ実行する")
    for item in items:
        if "tests/e2e/" in item.nodeid:
            item.add_marker(skip)


def _run_dir() -> Path | None:
    """結果と合図を置くフォルダ（`DEV_DOCS_RUN_DIR`）を返す。指定が無ければ `None`。"""
    value = os.environ.get(RUN_DIR_ENV, "")
    return Path(value) if value else None


def pytest_runtest_setup() -> None:
    """中断の合図ファイル（`$RUN_DIR/abort`）があれば、このテストを未実行として飛ばす。"""
    run_dir = _run_dir()
    if run_dir is not None and (run_dir / "abort").exists():
        pytest.skip(f"中断の合図（{run_dir / 'abort'}）により未実行です")


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """テスト 1 件の結果が確定するたびに `$RUN_DIR/results.jsonl` へ書き足す。"""
    run_dir = _run_dir()
    if run_dir is None:
        return
    # setup / teardown は失敗したとき・飛ばされたときだけ記録する（正常時は call の結果で足りる）
    if report.when != "call" and report.outcome not in ("failed", "skipped"):
        return
    reason = report.longreprtext or ""
    aborted = "中断の合図" in reason and report.outcome == "skipped"
    entry = {
        "test_id": report.nodeid,
        "phase": report.when,
        "outcome": NOT_RUN if aborted else report.outcome,
        "duration_sec": round(report.duration, 1),
        "reason": reason[-REASON_MAX_CHARS:],
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ToolResult:
    """MCP のツールの呼び出し結果。"""

    is_error: bool
    text: str

    @property
    def data(self) -> Any:
        """本文を JSON として読んだ値を返す。"""
        return json.loads(self.text)


def call_tool(
    port: int,
    path: str,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_sec: float = HTTP_TIMEOUT_SEC,
) -> ToolResult:
    """`127.0.0.1:{port}` の MCP のツールを JSON-RPC の `tools/call` で呼ぶ。"""
    response = httpx.post(
        f"http://127.0.0.1:{port}{path}",
        headers=MCP_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        timeout=timeout_sec,
    )
    result = response.json()["result"]
    return ToolResult(
        is_error=bool(result.get("isError")),
        text="".join(part["text"] for part in result["content"] if part["type"] == "text"),
    )


def list_tools(port: int, path: str = "/mcp/") -> list[str]:
    """`127.0.0.1:{port}` の MCP のツールの名前を並べる。"""
    response = httpx.post(
        f"http://127.0.0.1:{port}{path}",
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        timeout=HTTP_TIMEOUT_SEC,
    )
    return [tool["name"] for tool in response.json()["result"]["tools"]]


@dataclass
class SourceSpec:
    """端末の設定に並べる配信元 1 つ（フォルダと権限）。"""

    id: str
    folder: Path
    config: list[Path]
    scope_read: list[Path]
    scope_write: list[Path] | None = None
    enabled: bool = True
    outside_read: bool | None = None


@dataclass
class Served:
    """子プロセスで動く `dev-docs serve` と、HTTP の呼び出しの道具。"""

    process: subprocess.Popen[bytes]
    port: int
    settings: Path
    stdout_path: Path
    stderr_path: Path
    folders: dict[str, Path] = field(default_factory=dict)

    def url(self, path: str) -> str:
        """待ち受けのアドレスに path をつなげた URL を返す。"""
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str, **params: str) -> httpx.Response:
        """画面の API を GET で呼ぶ。"""
        return httpx.get(self.url(path), params=params, timeout=HTTP_TIMEOUT_SEC)

    def post_admin(self, payload: dict[str, Any]) -> httpx.Response:
        """`/_admin/mcp` へ JSON-RPC を送る。"""
        return httpx.post(
            self.url("/_admin/mcp/"), headers=MCP_HEADERS, json=payload, timeout=HTTP_TIMEOUT_SEC
        )

    def tool_names(self) -> list[str]:
        """`/mcp` のツールの名前を並べる。"""
        response = self._post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        return [tool["name"] for tool in response.json()["result"]["tools"]]

    def call(self, name: str, **arguments: Any) -> ToolResult:
        """`/mcp` のツールを HTTP で呼ぶ。"""
        return call_tool(self.port, "/mcp/", name, arguments)

    def call_admin(self, name: str, **arguments: Any) -> ToolResult:
        """`/_admin/mcp` のツールを HTTP で呼ぶ。"""
        return call_tool(self.port, "/_admin/mcp/", name, arguments)

    def update(self) -> ToolResult:
        """`/_admin/mcp` の `update` を呼ぶ（`git pull` と `uv sync` を待つため長く待つ）。"""
        return call_tool(self.port, "/_admin/mcp/", "update", {}, timeout_sec=UPDATE_TIMEOUT_SEC)

    def stdout(self) -> str:
        """ここまでの標準出力を返す。"""
        return self.stdout_path.read_text(encoding="utf-8")

    def stderr(self) -> str:
        """ここまでの標準エラーを返す。"""
        return self.stderr_path.read_text(encoding="utf-8")

    def listening_addresses(self) -> set[str]:
        """ポートで待ち受けているローカルアドレス（16 進）を /proc から集める。"""
        return listening_addresses(self.port)

    def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        """JSON-RPC を 1 つ送る。"""
        return httpx.post(
            self.url(path), headers=MCP_HEADERS, json=payload, timeout=HTTP_TIMEOUT_SEC
        )


def listening_addresses(port: int) -> set[str]:
    """ポートで待ち受けているローカルアドレス（16 進）を /proc から集める。"""
    found: set[str] = set()
    for table in TCP_TABLES:
        for line in Path(table).read_text(encoding="utf-8").splitlines()[1:]:
            columns = line.split()
            address, local_port = columns[1].split(":")
            if columns[3] == LISTEN_STATE and int(local_port, 16) == port:
                found.add(address)
    return found


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
    """配信元のフォルダ（git リポジトリか Git 管理外）を作り、端末の設定に並べる情報を返す関数を返す。"""

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
        outside_read: bool | None = None,
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
            outside_read=outside_read,
        )

    return _make


@pytest.fixture
def add_worktree(run_git: Callable[..., str]) -> Callable[..., Path]:
    """git リポジトリの `.claude/worktrees/{name}` にワークツリーを作り、そのパスを返す関数を返す。"""

    def _add(repo: Path, name: str = "x") -> Path:
        path = repo / ".claude" / "worktrees" / name
        run_git(repo, "worktree", "add", "-b", f"feat/{name}", str(path))
        return path

    return _add


def _settings_text(
    root: Path,
    specs: list[SourceSpec],
    *,
    clone: Path | None = None,
    version: str = "1",
    extra: str = "",
) -> str:
    """端末の設定の YAML を組み立てる。"""
    lines = [
        f'version: "{version}"',
        f"clone: {clone if clone is not None else root / 'clone'}",
        f"state_dir: {root / 'state'}",
    ]
    if extra:
        lines.append(extra.rstrip("\n"))
    lines.append("sources:" if specs else "sources: []")
    for spec in specs:
        lines.append(f"  - id: {spec.id}")
        lines.append("    config:")
        lines.extend(f"      - {path}" for path in spec.config)
        if not spec.enabled:
            lines.append("    enabled: false")
        if spec.outside_read is not None:
            lines.append(f"    outside_read: {str(spec.outside_read).lower()}")
        lines.append("    scope:")
        lines.append("      read:")
        lines.extend(f"        - {path}" for path in spec.scope_read)
        if spec.scope_write is not None:
            lines.append("      write:")
            lines.extend(f"        - {path}" for path in spec.scope_write)
    return "\n".join(lines) + "\n"


@pytest.fixture
def write_settings(tmp_path: Path) -> Callable[..., Path]:
    """端末の設定の YAML を書いて、そのパスを返す関数を返す。"""

    def _write(
        *specs: SourceSpec,
        name: str = "settings.yaml",
        clone: Path | None = None,
        version: str = "1",
        extra: str = "",
    ) -> Path:
        path = tmp_path / name
        text = _settings_text(tmp_path, list(specs), clone=clone, version=version, extra=extra)
        path.write_text(text, encoding="utf-8")
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
def launch(tmp_path: Path) -> Iterator[Callable[..., Served]]:
    """`dev-docs serve` を子プロセスで起動する関数を返す（終了時に止める）。"""
    started: list[Served] = []
    counter = iter(range(1000))

    def _launch(
        settings: Path, port: int, *, python: Path | None = None, cwd: Path | None = None
    ) -> Served:
        number = next(counter)
        stdout_path = tmp_path / f"serve-{number}.stdout"
        stderr_path = tmp_path / f"serve-{number}.stderr"
        env = {**os.environ, "DEV_DOCS_CONFIG": str(settings), "DEV_DOCS_PORT": str(port)}
        interpreter = str(python) if python is not None else sys.executable
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            process = subprocess.Popen(
                [interpreter, "-m", "dev_docs", "serve"], env=env, cwd=cwd, stdout=out, stderr=err
            )
        served = Served(process, port, settings, stdout_path, stderr_path)
        started.append(served)
        return served

    yield _launch
    for served in started:
        if served.process.poll() is None:
            served.process.terminate()
            served.process.wait(timeout=SERVE_TIMEOUT_SEC)


def _wait_until_serving(served: Served) -> None:
    """子プロセスが画面の API で応答するまで待つ。"""
    deadline = time.monotonic() + SERVE_TIMEOUT_SEC
    while time.monotonic() < deadline:
        assert served.process.poll() is None, f"dev-docs serve が先に終わった\n{served.stderr()}"
        try:
            response = httpx.get(served.url("/_api/openapi.json"), timeout=1)
        except httpx.TransportError:
            time.sleep(0.2)
            continue
        if response.status_code == 200:
            return
    message = "dev-docs serve が待ち受けを始めなかった"
    raise AssertionError(message)


@pytest.fixture
def serve(
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    launch: Callable[..., Served],
) -> Callable[..., Served]:
    """配信元を並べた端末の設定で `dev-docs serve` を起動し、応答するまで待つ関数を返す。"""

    def _serve(
        *specs: SourceSpec, clone: Path | None = None, extra: str = "", port: int | None = None
    ) -> Served:
        settings = write_settings(*specs, clone=clone, extra=extra)
        served = launch(settings, port if port is not None else free_port())
        served.folders.update({spec.id: spec.folder for spec in specs})
        _wait_until_serving(served)
        return served

    return _serve


# === 状態の確かめと待ちの道具 ===


def serve_pids(port: int) -> list[int]:
    """`DEV_DOCS_PORT` が `port` の `dev-docs serve` のプロセス ID を /proc から集める。"""
    marker = f"DEV_DOCS_PORT={port}".encode()
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().split(b"\0")
            environment = (entry / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"dev_docs" in command and b"serve" in command and marker in environment:
            found.append(int(entry.name))
    return sorted(found)


def wait_for_port(port: int, timeout_sec: float = START_WAIT_SEC) -> None:
    """`127.0.0.1:{port}` の画面の API が応答するまで待つ。"""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/_api/openapi.json", timeout=1).is_success:
                return
        except httpx.TransportError:
            pass
        time.sleep(POLL_INTERVAL_SEC)
    message = f"{port} の待ち受けが始まらなかった"
    raise AssertionError(message)


def wait_for_version(port: int, version: str, timeout_sec: float = RESTART_WAIT_SEC) -> Any:
    """管理の MCP の `status` が `version` を返すまで待ち、その結果（JSON）を返す。"""
    deadline = time.monotonic() + timeout_sec
    seen = "応答なし"
    while time.monotonic() < deadline:
        try:
            data = call_tool(port, "/_admin/mcp/", "status", {"format": "json"}).data
        except httpx.HTTPError, ValueError, KeyError:
            data = None
        if data is not None:
            if data["version"] == version:
                return data
            seen = data["version"]
        time.sleep(POLL_INTERVAL_SEC)
    message = f"status が {version} を返さなかった（最後に見たバージョン: {seen}）"
    raise AssertionError(message)


def stop_servers(port: int) -> None:
    """`port` で動く `dev-docs serve` を止める。"""
    for pid in serve_pids(port):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    deadline = time.monotonic() + SERVE_TIMEOUT_SEC
    while serve_pids(port) and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SEC)
    for pid in serve_pids(port):
        os.kill(pid, signal.SIGKILL)


@pytest.fixture
def list_mcp_tools() -> Callable[..., list[str]]:
    """ポートで待ち受ける MCP のツールの名前を並べる関数を返す。"""
    return list_tools


@pytest.fixture
def serve_pid_count() -> Callable[[int], int]:
    """ポートで動く `dev-docs serve` のプロセスの数を返す関数を返す。"""

    def _count(port: int) -> int:
        return len(serve_pids(port))

    return _count


@pytest.fixture
def wait_for_server() -> Callable[..., None]:
    """ポートの画面の API が応答するまで待つ関数を返す。"""
    return wait_for_port


@pytest.fixture
def wait_for_new_version() -> Callable[..., Any]:
    """管理の MCP の `status` が指したバージョンを返すまで待つ関数を返す。"""
    return wait_for_version


@pytest.fixture
def call_mcp_tool() -> Callable[..., ToolResult]:
    """ポートの MCP のツールを呼ぶ関数を返す（`call_mcp_tool(port, path, name, **引数)`）。"""

    def _call(port: int, path: str, name: str, **arguments: Any) -> ToolResult:
        return call_tool(port, path, name, arguments)

    return _call


@pytest.fixture
def update_server() -> Callable[[int], ToolResult]:
    """ポートの管理の MCP の `update` を、`git pull` と `uv sync` を待つ長さで呼ぶ関数を返す。"""

    def _update(port: int) -> ToolResult:
        return call_tool(port, "/_admin/mcp/", "update", {}, timeout_sec=UPDATE_TIMEOUT_SEC)

    return _update


@pytest.fixture
def snapshot() -> Callable[[Path], dict[str, bytes]]:
    """フォルダの下のファイルのパスと中身を集める関数を返す（`.git` の下は除く）。"""

    def _snapshot(folder: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(folder)): path.read_bytes()
            for path in sorted(folder.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(folder).parts
        }

    return _snapshot


@pytest.fixture
def load_yaml_file() -> Callable[[Path], Any]:
    """YAML のファイルを読んだ値を返す関数を返す。"""

    def _load(path: Path) -> Any:
        return YAML(typ="safe").load(path.read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def schema_errors() -> Callable[[Path, Any], list[str]]:
    """YAML のスキーマで値を検証し、違反の文を並べる関数を返す。"""

    def _errors(schema_file: Path, value: Any) -> list[str]:
        schema = YAML(typ="safe").load(schema_file.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        return [error.message for error in validator.iter_errors(value)]

    return _errors


# === dev-docs のクローン ===

REPO_ROOT = Path(__file__).parents[2]
CLONE_FILES = (
    "src",
    "content",
    "templates",
    "plugins",
    ".claude-plugin",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)
SETTINGS_QUERY = "src/dev_docs/features/settings/query.py"
SETTINGS_SCHEMA_FILE = "src/dev_docs/schemas/settings.schema.yaml"
NEXT_SETTINGS_PROPERTY = """\
  script_timeout_seconds:
    type: integer
    title: スクリプトの制限時間（秒）
    minimum: 1
"""


@dataclass
class DevDocsClone:
    """上流の bare リポジトリと、その dev-docs のクローン。"""

    root: Path
    work: Path
    bare: Path
    clone: Path
    run_git: Callable[..., str]

    @property
    def python(self) -> Path:
        """クローンの `.venv` の Python。"""
        return self.clone / ".venv" / "bin" / "python"

    @property
    def version(self) -> str:
        """クローンの `pyproject.toml` の dev-docs のバージョンを返す。"""
        pyproject = (self.clone / "pyproject.toml").read_text(encoding="utf-8")
        return next(
            line.split('"')[1] for line in pyproject.splitlines() if line.startswith("version = ")
        )

    def head(self) -> str:
        """クローンの HEAD の SHA を返す。"""
        return self.run_git(self.clone, "rev-parse", "HEAD").strip()

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

    def next_settings_version(self, steps: str, root: Path | None = None) -> dict[str, str]:
        """端末の設定のバージョンを 1 つ上げ、`steps` の移し替えの手順を持つファイル一式を返す。

        `script_timeout_sec` を `script_timeout_seconds` に改名できるよう、スキーマに新しいキーを追加する。
        """
        base = root if root is not None else self.work
        query = (base / SETTINGS_QUERY).read_text(encoding="utf-8")
        schema = (base / SETTINGS_SCHEMA_FILE).read_text(encoding="utf-8")
        assert 'SETTINGS_VERSION = "1"' in query
        assert schema.endswith("    minimum: 1\n")
        return {
            SETTINGS_QUERY: query.replace('SETTINGS_VERSION = "1"', 'SETTINGS_VERSION = "2"'),
            SETTINGS_SCHEMA_FILE: schema + NEXT_SETTINGS_PROPERTY,
            "src/dev_docs/migrations/settings/2/steps.yaml": steps,
        }

    def write_local(self, files: dict[str, str]) -> None:
        """クローンの作業ツリーにファイルを書く（commit しない）。"""
        for name, content in files.items():
            target = self.clone / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def migrate(self, settings: Path, *args: str) -> subprocess.CompletedProcess[str]:
        """クローンの Python で `dev-docs migrate` を実行する。"""
        return subprocess.run(
            [str(self.python), "-m", "dev_docs", "migrate", *args],
            cwd=self.clone,
            env={**os.environ, "DEV_DOCS_CONFIG": str(settings)},
            capture_output=True,
            text=True,
            timeout=SERVE_TIMEOUT_SEC,
            check=False,
        )


@pytest.fixture
def make_clone(
    tmp_path: Path, run_git: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> Callable[..., DevDocsClone]:
    """dev-docs 自身の小さなコピーを上流にしたクローンを `{tmp}/clone` に作る関数を返す。"""
    # 依存はキャッシュから入れる（ネットワークを使わない。`update` の `uv sync` も同じ）
    monkeypatch.setenv("UV_OFFLINE", "1")

    def _make(*, sync: bool = True) -> DevDocsClone:
        work = tmp_path / "upstream-work"
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
        bare = tmp_path / "upstream.git"
        run_git(tmp_path, "clone", "--bare", str(work), str(bare))
        clone = tmp_path / "clone"
        run_git(tmp_path, "clone", str(bare), str(clone))
        if sync:
            subprocess.run(["uv", "sync"], cwd=clone, check=True, capture_output=True)
        return DevDocsClone(tmp_path, work, bare, clone, run_git)

    return _make


@pytest.fixture
def serve_from_clone(
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    launch: Callable[..., Served],
) -> Callable[..., Served]:
    """クローンの `.venv` の Python で `dev-docs serve` を起動し、応答するまで待つ関数を返す。"""

    def _serve(
        clone: DevDocsClone, *specs: SourceSpec, extra: str = "", port: int | None = None
    ) -> Served:
        settings = write_settings(*specs, clone=clone.clone, extra=extra)
        served = launch(
            settings,
            port if port is not None else free_port(),
            python=clone.python,
            cwd=clone.clone,
        )
        served.folders.update({spec.id: spec.folder for spec in specs})
        _wait_until_serving(served)
        return served

    return _serve


# === Claude Code（claude -p）を動かす道具 ===

CLAUDE_BIN = "claude"
CLAUDE_MODEL_ENV = "DEV_DOCS_E2E_CLAUDE_MODEL"
DEFAULT_CLAUDE_MODEL = "sonnet"
CLAUDE_AUTH_ENVS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
CLAUDE_RUN_TIMEOUT_SEC = 900
CLAUDE_COMMAND_TIMEOUT_SEC = 180
CLAUDE_EXIT_TIMEOUT_SEC = 60
MARKETPLACE_SOURCE = REPO_ROOT
PLUGIN_ID = "dev-docs@dev-docs"
DOCS_TOOL_PREFIX = "mcp__plugin_dev-docs_dev-docs__"
ENV_MARKER = ("E2E_KEEP", "keep")
REAL_FILES = (
    "settings.json",
    "plugins/installed_plugins.json",
    "plugins/known_marketplaces.json",
)


def _fingerprint(path: Path) -> str:
    """ファイルの中身のハッシュを返す（ファイルが無ければ空の文字列）。"""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def real_fingerprints() -> dict[str, str]:
    """テストが変えてはいけない、端末の `~/.claude` と `~/.config/dev-docs` の中身のハッシュを集める。"""
    found: dict[str, str] = {}
    config_dirs = [Path.home() / ".claude"]
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        config_dirs.append(Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser())
    for directory in config_dirs:
        for name in REAL_FILES:
            found[str(directory / name)] = _fingerprint(directory / name)
    dev_docs_dir = Path.home() / ".config" / "dev-docs"
    if dev_docs_dir.is_dir():
        for path in sorted(dev_docs_dir.rglob("*")):
            found[str(path)] = _fingerprint(path)
    else:
        found[str(dev_docs_dir)] = ""
    return found


def _uv_directory(*command: str) -> str:
    """`uv` の置き場所を `uv cache dir` などで引く。"""
    result = subprocess.run(
        ["uv", *command], capture_output=True, text=True, timeout=30, check=False
    )
    return result.stdout.strip()


@dataclass
class ClaudeRun:
    """`claude -p` を 1 回動かした結果。"""

    events: list[dict[str, Any]]
    returncode: int
    stderr: str
    questions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def result(self) -> dict[str, Any]:
        """最後の `result` のイベント。"""
        results = [event for event in self.events if event.get("type") == "result"]
        assert results, f"claude の result が無い\n{self.stderr}"
        return results[-1]

    @property
    def text(self) -> str:
        """スキルの最後の応答。"""
        return str(self.result.get("result", ""))

    @property
    def init(self) -> dict[str, Any]:
        """セッションの `system` の `init` のイベント。"""
        inits = [
            event
            for event in self.events
            if event.get("type") == "system" and event.get("subtype") == "init"
        ]
        assert inits, f"claude の init が無い\n{self.stderr}"
        return inits[0]

    @property
    def tool_uses(self) -> list[tuple[str, dict[str, Any]]]:
        """モデルが呼んだツールの名前と入力。"""
        calls: list[tuple[str, dict[str, Any]]] = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append((block["name"], block.get("input", {})))
        return calls

    @property
    def question_texts(self) -> list[str]:
        """利用者に聞かれた質問の文。"""
        return [str(question.get("question", "")) for question in self.questions]

    def hook_responses(self, hook_event: str) -> list[dict[str, Any]]:
        """`hook_event` のフックの結果のイベント。"""
        return [
            event
            for event in self.events
            if event.get("type") == "system"
            and event.get("subtype") == "hook_response"
            and event.get("hook_event") == hook_event
        ]

    def session_start_context(self) -> tuple[int | None, str]:
        """SessionStart のフックの終了コードと、セッションの文脈に入れた文を返す。"""
        responses = self.hook_responses("SessionStart")
        assert responses, f"SessionStart のフックの結果が無い\n{self.stderr}"
        response = responses[-1]
        output = str(response.get("stdout") or response.get("output") or "")
        context = ""
        try:
            parsed = json.loads(output)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            context = str(parsed.get("hookSpecificOutput", {}).get("additionalContext", ""))
        return response.get("exit_code"), context


def _choose(question: dict[str, Any], rules: Sequence[tuple[str, str]]) -> str:
    """質問への答えを決める。`rules` の正規表現に当たればその答え、無ければ先頭の選択肢。"""
    text = f"{question.get('header', '')} {question.get('question', '')}"
    for pattern, answer in rules:
        if re.search(pattern, text):
            return answer
    options = question.get("options") or []
    return str(options[0]["label"]) if options else ""


def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    """標準入力へ JSON の 1 行を送る。"""
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _respond(
    process: subprocess.Popen[str],
    event: dict[str, Any],
    rules: Sequence[tuple[str, str]],
    questions: list[dict[str, Any]],
) -> None:
    """ツールの許可の要求に答える。AskUserQuestion は `rules` か先頭の選択肢で答える。"""
    request = event.get("request", {})
    request_id = event.get("request_id")
    if request.get("subtype") != "can_use_tool":
        reply: dict[str, Any] = {
            "subtype": "error",
            "request_id": request_id,
            "error": f"未対応の要求: {request.get('subtype')}",
        }
    else:
        tool_input = dict(request.get("input") or {})
        if request.get("tool_name") == "AskUserQuestion":
            asked = tool_input.get("questions", [])
            questions.extend(asked)
            tool_input["answers"] = {item["question"]: _choose(item, rules) for item in asked}
        reply = {
            "subtype": "success",
            "request_id": request_id,
            "response": {"behavior": "allow", "updatedInput": tool_input},
        }
    _send(process, {"type": "control_response", "response": reply})


@dataclass
class ClaudeHome:
    """テスト用の一時フォルダに作った Claude Code の設定の場所（プラグイン `dev-docs` をユーザースコープに入れてある）。"""

    root: Path
    config_dir: Path
    home: Path
    port: int
    env: dict[str, str]
    before: dict[str, str]

    def settings_json(self) -> dict[str, Any]:
        """設定の場所の `settings.json` を読む。"""
        path = self.config_dir / "settings.json"
        return dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}

    def set_env(self, **values: str) -> None:
        """`settings.json` の `env` に値を追加する。ほかのキーは変えない。"""
        data = self.settings_json()
        data.setdefault("env", {}).update(values)
        (self.config_dir / "settings.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def real_changes(self) -> list[str]:
        """テストを流した端末の `~/.claude` と `~/.config/dev-docs` で、変わったファイルを返す。"""
        after = real_fingerprints()
        return sorted(path for path in after if after[path] != self.before.get(path))

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        answers: Sequence[tuple[str, str]] = (),
        timeout_sec: float = CLAUDE_RUN_TIMEOUT_SEC,
    ) -> ClaudeRun:
        """`claude -p` で 1 回動かす。AskUserQuestion には `answers` か先頭の選択肢で答える。"""
        argv = [
            CLAUDE_BIN,
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-hook-events",
            "--permission-prompt-tool",
            "stdio",
            "--model",
            os.environ.get(CLAUDE_MODEL_ENV, DEFAULT_CLAUDE_MODEL),
            "--no-session-persistence",
        ]
        stderr_path = self.root / f"claude-{len(list(self.root.glob('claude-*.stderr')))}.stderr"
        with stderr_path.open("w", encoding="utf-8") as err:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=err,
                text=True,
                encoding="utf-8",
            )
        lines: queue.Queue[str | None] = queue.Queue()

        def _read() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()
        _send(process, {"type": "user", "message": {"role": "user", "content": prompt}})
        events: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []
        deadline = time.monotonic() + timeout_sec
        while True:
            if time.monotonic() > deadline:
                process.kill()
                message = f"claude が {timeout_sec} 秒で終わらなかった\n{stderr_path.read_text(encoding='utf-8')}"
                raise AssertionError(message)
            try:
                line = lines.get(timeout=5)
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                event = json.loads(line)
            except ValueError:
                continue
            events.append(event)
            if event.get("type") == "control_request":
                _respond(process, event, answers, questions)
            elif event.get("type") == "result":
                break
        assert process.stdin is not None
        process.stdin.close()
        try:
            returncode = process.wait(timeout=CLAUDE_EXIT_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
        # 読み取りを終えてから標準出力を閉じる（開きっぱなしの警告を残さない）
        reader.join(timeout=CLAUDE_EXIT_TIMEOUT_SEC)
        assert process.stdout is not None
        process.stdout.close()
        return ClaudeRun(events, returncode, stderr_path.read_text(encoding="utf-8"), questions)


@pytest.fixture
def claude_home(tmp_path: Path, free_port: Callable[[], int]) -> Iterator[ClaudeHome]:
    """`CLAUDE_CONFIG_DIR` と `HOME` を一時フォルダにした Claude Code の環境を作る（終了時に dev-docs を止める）。"""
    if not any(os.environ.get(name) for name in CLAUDE_AUTH_ENVS):
        pytest.fail(
            "claude -p の認証が無い。環境変数 CLAUDE_CODE_OAUTH_TOKEN（claude setup-token）か"
            " ANTHROPIC_API_KEY を渡す（端末の ~/.claude の認証は一時フォルダへコピーしない）",
            pytrace=False,
        )
    root = tmp_path / "claude"
    config_dir = root / "config"
    home = root / "home"
    config_dir.mkdir(parents=True)
    home.mkdir()
    (config_dir / ".claude.json").write_text(
        json.dumps({"hasCompletedOnboarding": True}), encoding="utf-8"
    )
    port = free_port()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CLAUDE", "DEV_DOCS_")) or key == "CLAUDE_CODE_OAUTH_TOKEN"
    }
    env.update(
        {
            "HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(config_dir),
            "DEV_DOCS_PORT": str(port),
            "UV_OFFLINE": "1",
            "UV_CACHE_DIR": _uv_directory("cache", "dir"),
            "UV_PYTHON_INSTALL_DIR": _uv_directory("python", "dir"),
        }
    )
    before = real_fingerprints()
    for command in (
        ["plugin", "marketplace", "add", str(MARKETPLACE_SOURCE), "--scope", "user"],
        ["plugin", "install", PLUGIN_ID, "--scope", "user"],
    ):
        result = subprocess.run(
            [CLAUDE_BIN, *command],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=CLAUDE_COMMAND_TIMEOUT_SEC,
            check=False,
        )
        assert result.returncode == 0, f"claude {' '.join(command)}\n{result.stdout}{result.stderr}"
    claude = ClaudeHome(root, config_dir, home, port, env, before)
    claude.set_env(**{ENV_MARKER[0]: ENV_MARKER[1]})
    yield claude
    stop_servers(port)


# === 画面をブラウザで確かめる道具 ===

BROWSER_TIMEOUT_MS = 15_000
SCREEN_SCHEMA = """\
type: object
title: 画面の確認
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
  summary:
    type: array
    title: まとめ
    x-heading: まとめ
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
SCREEN_NAV = (
    "nav:\n"
    "  tabs:\n"
    "    - title: 規約\n"
    "      items:\n"
    "        - auto:\n"
    "            document: sample\n"
    "    - title: 補足\n"
    "      items:\n"
    "        - page: sample/doc-2\n"
)
LONG_ROWS = 80


def _rows(prefix: str, count: int, notes: str) -> list[dict[str, str]]:
    """表の行を `count` 件作る。"""
    return [
        {"key": f"{prefix}{number}", "label": f"名称 {prefix}{number}", "notes": notes}
        for number in range(count)
    ]


@pytest.fixture
def page() -> Iterator[Page]:
    """画面を開くブラウザ（Chromium）のページを返す。クリップボードを読み書きでき、日本語・JST で動く。"""
    expect.set_options(timeout=BROWSER_TIMEOUT_MS)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            permissions=["clipboard-read", "clipboard-write"],
        )
        context.set_default_timeout(BROWSER_TIMEOUT_MS)
        yield context.new_page()
        context.close()
        browser.close()


@pytest.fixture
def screen_files() -> Callable[..., dict[str, str]]:
    """画面で読む配信元のファイル一式（`nav` つき・文書 1 は画面の高さを超える長さ）を作る関数を返す。"""

    def _files(
        *,
        summary_notes: str = "まとめの値",
        nav: bool = True,
        config_extra: str = "",
        **overrides: str,
    ) -> dict[str, str]:
        files = sample_files(
            **{
                "dev-docs.yaml": sample_config((SCREEN_NAV if nav else "") + config_extra),
                "schemas/sample.schema.yaml": SCREEN_SCHEMA,
                "docs/doc-1.yaml": sample_doc(
                    "doc-1",
                    "文書 1",
                    items=_rows("a", LONG_ROWS, "項目の備考"),
                    summary=_rows("s", 3, summary_notes),
                ),
                "docs/doc-2.yaml": sample_doc(
                    "doc-2",
                    "文書 2",
                    description="検索で当てるパンプキンの語",
                    items=_rows("b", 3, "文書 2 の備考"),
                    summary=_rows("t", 2, "文書 2 のまとめ"),
                ),
            }
        )
        files.update(overrides)
        return files

    return _files


# プロンプトを持つ配信元（setup の前は files の行だけを持つ）
PROMPT_BASE_CONFIG = """\
version: "3"
name: sample
description: プロンプトを持つ配信元
documents:
  - id: files
    paths: [files.yaml]
    title: ファイル
    schema: schemas/files.schema.yaml
    records: files
    body_file: path
"""
# setup がプロンプトの行の候補を了承されて書く行
PROMPT_ROWS = """\
  - id: prompts
    paths: [content/prompts/**/*.yaml]
    title: プロンプト
    schema: schemas/prompt.schema.yaml
    converter: prompt-doc
    metadata:
      name: name
      description: description
      tags: tags
  - id: prompts-sample
    paths: [plugins/sample/content/prompts/**/*.yaml]
    title: プロンプト
    schema: schemas/prompt.schema.yaml
    converter: prompt-doc
    metadata:
      name: name
      description: description
      tags: tags
converters:
  - id: prompt-doc
    run: [dev-docs, prompt-doc]
nav:
  tabs:
    - title: ファイル
      items:
        - auto:
            document: files
    - title: プロンプト
      items:
        - auto:
            document: prompts
            group_by: kind
        - auto:
            document: prompts-sample
            group_by: kind
"""
PROMPT_FILES_INDEX = "files:\n  - path: docs/a.md\n    name: A\n    description: A の説明\n"
PLUGIN_JSON = '{"name": "sample", "version": "0.1.0"}\n'

# A-42 の例 2（kind: llm）。言語は en・ja、例の組は no-logs
REFLECTION_HEAD = """\
id: node/reflection
name: 振り返りのノード
kind: llm
lang: en
description: キャラクターが最近の出来事を振り返り、性格特性の基底値の変化を決める
tags: [reflection]
vars:
  character:
    type: object
    required: true
    description: 振り返るキャラクター
    example: {id: hina, display_name: ひな}
    properties:
      id: {type: string, required: true, description: キャラクターの ID, example: hina}
      display_name: {type: string, required: true, description: 表示名, example: ひな}
  now:
    type: string
    required: true
    description: 今の日時の文
    example: 2026-10-31（金）21:00
  traits:
    type: array
    required: true
    description: 性格特性の定義と今の基底値
    source: DB のキャラクターの性格特性
    example:
      - {name: 好奇心, definition: 新しいものへの興味, base: 0.7}
    items:
      type: object
      description: 性格特性 1 件
      properties:
        name: {type: string, required: true, description: 特性の名前, example: 好奇心}
        definition: {type: string, required: true, description: 特性の定義, example: 新しいものへの興味}
        base: {type: number, required: true, description: 今の基底値（0〜1）, example: 0.7}
  logs:
    type: array
    required: true
    description: 振り返るログの行（古い順）
    example: ["10/31 20:10 コンビニで新作のプリンを買った"]
    items: {type: string, description: ログ 1 行}
output: write_trait_changes を 1 回呼んで終える
examples:
  - id: no-logs
    name: ログが無い
    values: {logs: []}
"""
# 例の組 broken（traits に文字列）
REFLECTION_BROKEN_EXAMPLE = """\
  - id: broken
    name: broken
    values: {traits: oops}
"""
REFLECTION_PARTS = """\
parts:
  - id: role
    role: system
    tags: [role]
    texts:
      - lang: en
        text: |-
          ### Role
          You are in charge of reflecting on the recent events of "{{ character.display_name }}" (character_id: {{ character.id }}).
          <rules>Decide the changes only from the logs.</rules>
      - lang: ja
        text: |-
          ### 役割
          あなたは、キャラクター「{{ character.display_name }}」（character_id: {{ character.id }}）の振り返りの担当です。
  - id: now
    role: user
    tags: [context]
    texts:
      - lang: en
        text: |-
          ### Now
          {{ now }}
      - lang: ja
        text: |-
          ### いま
          {{ now }}
  - id: traits
    role: user
    tags: [context]
    texts:
      - lang: en
        text: |-
          ### Personality trait definitions and current base values
          {% for t in traits -%}
          - {{ t.name }}: {{ t.definition }} (base {{ t.base }})
          {% endfor %}
      - lang: ja
        text: |-
          ### 性格特性の定義と今の基底値
          {% for t in traits -%}
          - {{ t.name }}: {{ t.definition }}（基底値 {{ t.base }}）
          {% endfor %}
  - id: logs
    role: user
    tags: [context]
    when: "{{ logs | length > 0 }}"
    texts:
      - lang: en
        text: |-
          ### Logs to reflect on (oldest first)
          {% for line in logs -%}
          - {{ line }}
          {% endfor %}
      - lang: ja
        text: |-
          ### 振り返るログ（古い順）
          {% for line in logs -%}
          - {{ line }}
          {% endfor %}
  - id: no-logs
    role: user
    tags: [context]
    when: "{{ logs | length == 0 }}"
    texts:
      - lang: en
        text: |-
          ### Logs to reflect on
          - none
      - lang: ja
        text: |-
          ### 振り返るログ
          - なし
"""

# A-42 の例 1（kind: hook）。言語は ja だけ
SESSION_CONTEXT_HEAD = """\
id: session-context
name: SessionStart の配信元の一覧
kind: hook
lang: ja
description: 作業場所から使える配信元と警告を、セッションの始めに伝える
tags: [sessionstart, 配信元]
vars:
  sources:
    type: array
    required: true
    description: 作業場所から使える配信元
    source: 端末の設定の sources[] のうち scope.read に作業場所が入るもの
    example:
      - {id: claude-balancer, access: read_write, description: 複数のアカウントを貸し出す基盤の設計書}
    items:
      type: object
      description: 配信元 1 件
      properties:
        id: {type: string, required: true, description: 配信元の ID, example: knowledge}
        access: {type: string, required: true, description: 権限, example: read}
        description: {type: string, description: 配信元の説明, example: 共通の規約}
  warnings:
    type: array
    description: 索引の同期のずれ・古い設定などの注意
    example: ["knowledge: 索引が 3 件ずれています"]
    items: {type: string, description: 注意 1 件}
examples:
  - id: no-source
    name: 配信元が無い
    values: {sources: [], warnings: []}
"""
# 配信元 20 件（描画した結果が 1,000 字を超える）の組 many-sources
MANY_SOURCES_EXAMPLE = (
    "  - id: many-sources\n"
    "    name: many-sources\n"
    "    values: {sources: ["
    + ", ".join(
        f"{{id: source-{n:02d}, access: read, description: "
        f"端末の設定で読み書きできる配信元の設計書と規約とテンプレートの一式その{n:02d}}}"
        for n in range(1, 21)
    )
    + "], warnings: []}\n"
)
SESSION_CONTEXT_PARTS = """\
parts:
  - id: sources
    when: "{{ sources | length > 0 }}"
    texts:
      - lang: ja
        text: |
          dev-docs で次の配信元を使えます。
          {% for s in sources %}- {{ s.id }}（{{ s.access }}）: {{ s.description }}
          {% endfor %}
  - id: no-source
    when: "{{ sources | length == 0 }}"
    texts:
      - lang: ja
        text: |
          この作業場所から使える dev-docs の配信元はありません。
  - id: warnings
    when: "{{ warnings }}"
    texts:
      - lang: ja
        text: |
          注意:
          {% for w in warnings %}- {{ w }}
          {% endfor %}
"""


@pytest.fixture
def prompt_files() -> Callable[..., dict[str, str]]:
    """直下とプラグインのルートの `content/prompts/` にプロンプトを持つ配信元のファイル一式を作る関数を返す。

    `rows` が真なら setup がプロンプトの行を書いた後（行・converters・nav・プロンプトのスキーマ）、偽なら前。
    """

    def _files(
        *, rows: bool = True, broken: bool = False, many_sources: bool = False
    ) -> dict[str, str]:
        templates = REPO_ROOT / "templates"
        files = {
            "dev-docs.yaml": PROMPT_BASE_CONFIG + (PROMPT_ROWS if rows else ""),
            "schemas/files.schema.yaml": (templates / "files.schema.yaml").read_text(
                encoding="utf-8"
            ),
            "files.yaml": PROMPT_FILES_INDEX,
            "docs/a.md": "# A\n\nA の説明。\n",
            "content/prompts/node/reflection.yaml": (
                REFLECTION_HEAD + (REFLECTION_BROKEN_EXAMPLE if broken else "") + REFLECTION_PARTS
            ),
            "plugins/sample/.claude-plugin/plugin.json": PLUGIN_JSON,
            "plugins/sample/content/prompts/session-context.yaml": (
                SESSION_CONTEXT_HEAD
                + (MANY_SOURCES_EXAMPLE if many_sources else "")
                + SESSION_CONTEXT_PARTS
            ),
        }
        if rows:
            files["schemas/prompt.schema.yaml"] = (templates / "prompt.schema.yaml").read_text(
                encoding="utf-8"
            )
        return files

    return _files
