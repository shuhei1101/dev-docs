from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

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
# 起動の待ち受けを待つ上限。2026-11-12 の実測で、負荷の低いときは 1 回 18 秒、
# ロードアベレージ 20 では 30 秒を超えたため、30 秒 + 50% の余裕を持たせて 60 秒にする
SERVE_WAIT_SEC = 60
# 保留した応答を待つ上限
HOLD_WAIT_SEC = 60
SETTINGS_PATH = "/home/u/.config/project-index/settings.yaml"

# 名前・概要・タグ・項目の表を持つ種類のスキーマ（project-index が解いて返す値）
SAMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "title": "サンプル",
    "properties": {
        "id": {"type": "string", "title": "ID"},
        "name": {"type": "string", "title": "名前"},
        "description": {"type": "string", "title": "概要"},
        "tags": {"type": "array", "title": "タグ", "items": {"type": "string"}},
        "items": {
            "type": "array",
            "title": "項目",
            "x-heading": "項目",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "title": "キー"},
                    "label": {"type": "string", "title": "名称"},
                    "notes": {"type": "string", "title": "備考"},
                },
            },
        },
    },
    "required": ["id", "name"],
}


def row(
    row_id: str, paths: list[str], schema: dict[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    """配信元の設定の文書の行の JSON を作る。"""
    return {"id": row_id, "paths": paths, "schema": schema or SAMPLE_SCHEMA, **extra}


def doc(
    doc_id: str,
    path: str,
    *,
    kind: str = "sample",
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    version: str | None = None,
    record_index: int | None = None,
    body_path: str | None = None,
    body: str = "",
    updated: str = "2026-11-01T10:00:00+09:00",
) -> dict[str, Any]:
    """project-index の文書 1 件の JSON を作る（`data` を省くと `id` と `name` だけ）。"""
    values = data if data is not None else {"id": doc_id, "name": doc_id}
    return {
        "id": doc_id,
        "kind": kind,
        "path": path,
        "recordIndex": record_index,
        "bodyPath": body_path,
        "data": values,
        "metadata": metadata if metadata is not None else values,
        "version": version if version is not None else f"v-{doc_id}",
        "body": body,
        "updated": updated,
    }


@dataclass
class IndexSource:
    """モックが配信する配信元 1 つ。`docs` はリビジョン（`None` は既定）→ 文書の並び。"""

    documents: list[dict[str, Any]] = field(
        default_factory=lambda: [row("sample", ["docs/*.yaml"])]
    )
    docs: dict[str | None, list[dict[str, Any]]] = field(default_factory=dict)
    nav: dict[str, Any] | None = None
    git: bool = True
    default_ref: str = "develop"
    decision_folders: list[str] = field(default_factory=list)
    unreadable: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: dict[str, int] = field(default_factory=dict)
    decision_texts: dict[str, str] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=lambda: {"totalCount": 0, "items": []})
    refs: dict[str, Any] | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    config_version: dict[str, str] | None = None

    def config(self, source_id: str) -> dict[str, Any]:
        """`GET /sources/{source}/config` の応答。"""
        return {
            "id": source_id,
            "git": self.git,
            "defaultRef": self.default_ref if self.git else None,
            "nav": self.nav,
            "documents": self.documents,
            "decisions": {"folders": self.decision_folders},
            "github": {},
            "diffIgnoreKeys": ["updated"],
        }


class MockIndex:
    """project-index の読み取り API と端末の設定の API を、127.0.0.1 の空きポートで待ち受ける偽物。

    端末の設定の行（`rows`）の順に配信元の状態を決め、`sources` の配信元の文書を返す。

    入出力は shuhei1101/project-index#14 の Issue に記載した入出力に沿う（本物との食い違いは
    `docs/external-api/API-155-1.yaml`、本物への付け替えは #164）。
    """

    def __init__(self) -> None:
        self.sources: dict[str, IndexSource] = {}
        self.rows: list[dict[str, Any]] = []
        self.pending: set[int] = set()
        self.queued: dict[tuple[str, str], list[tuple[int, Any]]] = {}
        self.received: list[tuple[str, str, Any]] = []
        self.delay_sec = 0.0
        self.hold = threading.Event()
        self.hold.set()
        self.port = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> str:
        """待ち受けているアドレス。"""
        return f"http://127.0.0.1:{self.port}"

    def serve(
        self, source_id: str, source: IndexSource | None = None, **row_values: Any
    ) -> IndexSource:
        """配信元を足し、端末の設定の行にも並べる。"""
        found = source or IndexSource()
        self.sources[source_id] = found
        self.rows.append(
            {"id": source_id, "config": [f"/repo/{source_id}/project-index.yaml"], **row_values}
        )
        return found

    def start(self, port: int = 0) -> None:
        """待ち受けを始める（`port` が 0 なら空きポート）。"""
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else None
                status, value = mock.answer(self.command, self.path, body)
                payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    return

            do_GET = do_POST = do_PUT = _answer

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self._server.daemon_threads = True
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """待ち受けを止める（ポートは閉じる）。"""
        self.hold.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def _state(self, index: int, values: dict[str, Any]) -> dict[str, Any]:
        """端末の設定の行の配信元の状態。"""
        source_id = values.get("id")
        if index in self.pending:
            return {"id": None, "status": "pending_reload", "errors": []}
        if values.get("enabled") is False:
            return {"id": source_id, "status": "disabled", "errors": []}
        source = self.sources.get(str(source_id))
        if source is None or source.errors:
            errors = (
                source.errors if source is not None else [{"path": "config[0]", "reason": "無い"}]
            )
            return {"id": source_id, "status": "not_served", "errors": errors}
        state: dict[str, Any] = {"id": source_id, "status": "serving", "errors": []}
        if source.config_version is not None:
            state["configVersion"] = source.config_version
        return state

    def _settings(self) -> dict[str, Any]:
        """`GET /settings/sources` の応答。"""
        return {
            "settingsPath": SETTINGS_PATH,
            "sources": [
                {"row": values, **self._state(index, values)}
                for index, values in enumerate(self.rows)
            ],
        }

    def _served(self, source_id: str) -> tuple[IndexSource | None, tuple[int, Any] | None]:
        """配信中の配信元か、配信していない理由の 404 を返す。"""
        for index, values in enumerate(self.rows):
            if values.get("id") != source_id:
                continue
            state = self._state(index, values)
            if state["status"] == "serving":
                return self.sources[source_id], None
            if state["status"] == "not_served":
                missing = {"missing": "not_served", "value": source_id, "errors": state["errors"]}
                return None, (404, missing)
        return None, (404, {"missing": "source", "value": source_id})

    def answer(self, method: str, raw_path: str, body: Any) -> tuple[int, Any]:
        """要求 1 つに答える。"""
        self.received.append((method, raw_path, body))
        self.hold.wait(HOLD_WAIT_SEC)
        if self.delay_sec:
            time.sleep(self.delay_sec)
        url = urlsplit(raw_path)
        path = unquote(url.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        queued = self.queued.get((method, path))
        if queued:
            return queued.pop(0)
        parts = path.strip("/").split("/")
        if parts == ["sources"]:
            return 200, {
                "sources": [
                    self._state(i, r) for i, r in enumerate(self.rows) if i not in self.pending
                ]
            }
        if parts == ["settings", "sources"]:
            return self._settings_answer(method, body)
        source, missing = self._served(parts[1])
        if source is None:
            return missing or (404, {})
        return self._source_answer(parts[1], source, parts[2:], query)

    def _settings_answer(self, method: str, body: Any) -> tuple[int, Any]:
        """端末の設定の API に答える。"""
        if method == "PUT":
            self.rows = list(body["sources"])
            self.pending = set()
            return 200, self._settings()
        if method == "POST":
            same_id = next((r for r in self.rows if r.get("id") == body.get("id")), None)
            if same_id is not None:
                return 409, {"same": same_id == body}
            self.rows.append(body)
            return 201, {}
        return 200, self._settings()

    def _source_answer(
        self, source_id: str, source: IndexSource, rest: list[str], query: dict[str, str]
    ) -> tuple[int, Any]:
        """`/sources/{source}/...` に答える。"""
        ref = query.get("ref")
        if rest == ["config"]:
            return 200, source.config(source_id)
        if rest[0] == "docs":
            if ref is not None and ref not in source.docs:
                return 404, {"missing": "ref", "value": ref}
            listed = source.docs.get(ref, [])
            if len(rest) == 1:
                return 200, {
                    "ref": ref or (source.default_ref if source.git else None),
                    "documents": listed,
                    "unreadable": source.unreadable,
                }
            file = "/".join(rest[1:])
            found = next(
                (
                    item
                    for item in listed
                    if file in (item["path"], item.get("bodyPath"))
                    and query.get("id") in (None, item["id"])
                ),
                None,
            )
            extra = source.details.get(file)
            if found is None and extra is None:
                return 404, {"missing": "doc", "value": file}
            return 200, {"document": found, **(extra or {})}
        if rest == ["decisions"]:
            return 200, {"counts": source.decisions}
        if rest[0] == "decisions":
            text = source.decision_texts.get(rest[1])
            if text is None:
                return 404, {"missing": "doc", "value": rest[1]}
            return 200, {"markdown": text}
        if rest == ["search"]:
            if ref is not None and ref not in source.docs:
                return 404, {"missing": "ref", "value": ref}
            return 200, source.search
        refs = source.refs or {
            "git": source.git,
            "defaultRef": source.default_ref,
            "branches": [],
            "tags": [],
            "commits": [],
        }
        return 200, refs


@pytest.fixture
def mock_index() -> Iterator[MockIndex]:
    """空きポートで待ち受ける project-index の偽物を返す（終了時に止める）。"""
    mock = MockIndex()
    mock.start()
    yield mock
    mock.stop()


def sample_docs() -> list[dict[str, Any]]:
    """配信元 sample の文書 1・文書 2 を作る。"""
    return [
        doc("doc-1", "docs/doc-1.yaml", data={"id": "doc-1", "name": "文書 1"}),
        doc("doc-2", "docs/doc-2.yaml", data={"id": "doc-2", "name": "文書 2"}),
    ]


@pytest.fixture
def sample_index(mock_index: MockIndex) -> MockIndex:
    """文書 1・文書 2 を持つ配信元 sample を配信している project-index の偽物を返す。"""
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    return mock_index


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
class ServerEnv:
    """端末の設定から作ったアプリと、呼び出しの道具。"""

    settings_path: Path
    state_dir: Path
    handlers: Handlers
    client: TestClient

    def call_admin(self, name: str, **arguments: Any) -> ToolResult:
        """`/_admin/mcp` のツールを HTTP で呼ぶ。"""
        response = self.client.post(
            "/_admin/mcp/",
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


def settings_text(tmp_path: Path, address: str, extra: str = "") -> str:
    """dev-docs の端末の設定（version 2）の本文を作る。"""
    return (
        f'version: "2"\nclone: {tmp_path / "clone"}\nstate_dir: {tmp_path / "state"}\n'
        f"project_index: {address}\n{extra}"
    )


@pytest.fixture
def make_server(tmp_path: Path) -> Iterator[Callable[..., ServerEnv]]:
    """project-index の偽物につなぐ端末の設定でアプリを作り、テストのクライアントを返す関数を返す。"""
    with ExitStack() as stack:

        def _make(mock: MockIndex, *, screen_dir: Path | None = None, extra: str = "") -> ServerEnv:
            path = tmp_path / "settings.yaml"
            path.write_text(settings_text(tmp_path, mock.address, extra), encoding="utf-8")
            terminal = load_terminal_config(path)
            handlers = build_handlers(terminal)
            app = (
                build_app(handlers)
                if screen_dir is None
                else build_app(handlers, screen_dir=screen_dir)
            )
            client = stack.enter_context(TestClient(app, base_url=LOCAL_BASE_URL))
            return ServerEnv(path, terminal.state_dir, handlers, client)

        yield _make


@pytest.fixture
def write_settings(tmp_path: Path) -> Callable[..., Path]:
    """dev-docs の端末の設定を書いて、そのパスを返す関数を返す。"""

    def _write(address: str, *, extra: str = "", name: str = "settings.yaml") -> Path:
        path = tmp_path / name
        path.write_text(settings_text(tmp_path, address, extra), encoding="utf-8")
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

    def _start(
        settings: Path | None, port: int, *, extra_env: dict[str, str] | None = None
    ) -> subprocess.Popen[str]:
        # settings が None のときは DEV_DOCS_CONFIG を渡さず、既定のパスを読ませる
        env = {key: value for key, value in os.environ.items() if key != "DEV_DOCS_CONFIG"}
        env["DEV_DOCS_PORT"] = str(port)
        if settings is not None:
            env["DEV_DOCS_CONFIG"] = str(settings)
        env.update(extra_env or {})
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

    def _wait(
        process: subprocess.Popen[str], port: int, timeout_sec: float = SERVE_WAIT_SEC
    ) -> None:
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


REPO_ROOT = Path(__file__).parents[3]
CLONE_FILES = ("src", "content", "templates", "pyproject.toml", "uv.lock", ".python-version")


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
