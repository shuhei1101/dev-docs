from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

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


@dataclass
class SourceSpec:
    """端末の設定に並べる配信元 1 つ（フォルダと権限）。"""

    id: str
    folder: Path
    config: list[Path]
    scope_read: list[Path]
    scope_write: list[Path] | None = None


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
        response = self._post(
            "/mcp/",
            {
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
        )

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
        "    type: yaml\n"
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


def _settings_text(root: Path, specs: list[SourceSpec]) -> str:
    """端末の設定の YAML を組み立てる。"""
    lines = [
        'version: "1"',
        f"clone: {root / 'clone'}",
        f"state_dir: {root / 'state'}",
        "sources:" if specs else "sources: []",
    ]
    for spec in specs:
        lines.append(f"  - id: {spec.id}")
        lines.append("    config:")
        lines.extend(f"      - {path}" for path in spec.config)
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

    def _write(*specs: SourceSpec, name: str = "settings.yaml") -> Path:
        path = tmp_path / name
        path.write_text(_settings_text(tmp_path, list(specs)), encoding="utf-8")
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

    def _launch(settings: Path, port: int) -> Served:
        number = next(counter)
        stdout_path = tmp_path / f"serve-{number}.stdout"
        stderr_path = tmp_path / f"serve-{number}.stderr"
        env = {**os.environ, "DEV_DOCS_CONFIG": str(settings), "DEV_DOCS_PORT": str(port)}
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            process = subprocess.Popen(
                [sys.executable, "-m", "dev_docs", "serve"], env=env, stdout=out, stderr=err
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

    def _serve(*specs: SourceSpec) -> Served:
        served = launch(write_settings(*specs), free_port())
        served.folders.update({spec.id: spec.folder for spec in specs})
        _wait_until_serving(served)
        return served

    return _serve
