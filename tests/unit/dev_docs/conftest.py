from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import pytest

from dev_docs.features.settings.types import TerminalConfig
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.integrations.project_index.types import DocumentRow, IndexedDocument, SourceView

RULE_SCHEMA = {
    "title": "rule",
    "type": "object",
    "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
    "required": ["id", "name"],
}


def doc_json(
    doc_id: str,
    path: str,
    *,
    kind: str = "rules",
    name: str | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    version: str | None = None,
    record_index: int | None = None,
    body_path: str | None = None,
    body: str = "",
    updated: str | None = "2026-11-01T10:00:00+09:00",
) -> dict[str, Any]:
    """偽物の project-index に置く文書 1 件を作る。

    `record_index` は使わない（行の文書の添字は、配信元の設定の `records` の行から呼び出し側が決める）。
    `body`・`updated` は文書の取得でだけ返す。
    """
    del record_index
    label = name if name is not None else doc_id.upper()
    meta = metadata if metadata is not None else {"id": doc_id, "name": label}
    return {
        "id": doc_id,
        "path": path,
        "kind": kind,
        "name": meta.get("name", label),
        "description": meta.get("description"),
        "tags": list(meta.get("tags") or []),
        "visibility": meta.get("visibility"),
        "bodyPath": body_path,
        "version": version if version is not None else f"v-{doc_id}",
        "value": data if data is not None else {"id": doc_id, "name": label},
        "_body": body,
        "_updated": updated,
    }


def list_entry(document: dict[str, Any], *, values: bool) -> dict[str, Any]:
    """偽物に置いた文書を、文書の一覧の 1 件（IF-24）にする。"""
    entry = {key: value for key, value in document.items() if not key.startswith("_")}
    if not values:
        entry["value"] = None
    return entry


def config_json(
    source: str = "sample",
    *,
    documents: list[dict[str, Any]] | None = None,
    nav: dict[str, Any] | None = None,
    git: bool = True,
    decisions: list[str] | None = None,
    github: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """偽物の project-index に置く配信元の設定を作る。

    `documents[].schema` には解いた種類のスキーマを入れる（偽物が `schemas` に分けて返す）。
    """
    return {
        "_source": source,
        "_git": git,
        "nav": nav,
        "documents": documents
        if documents is not None
        else [{"id": "rules", "paths": ["docs/*.yaml"], "schema": RULE_SCHEMA}],
        "decisions": {"folders": decisions or []},
        "github": github,
        "diff": {"ignore_keys": ["updated"]},
    }


def _config_response(config: dict[str, Any], *, schemas: bool) -> dict[str, Any]:
    """偽物に置いた配信元の設定を、配信元の設定の取得の応答（IF-23）にする。"""
    rows = [{**row, "schema": f"schemas/{row['id']}.schema.yaml"} for row in config["documents"]]
    body = {key: value for key, value in config.items() if not key.startswith("_")}
    body["documents"] = rows
    body["schemas"] = (
        {row["id"]: dict(row.get("schema") or {}) for row in config["documents"]}
        if schemas
        else None
    )
    return body


@dataclass
class FakeIndex:
    """project-index の読み取り API と端末の設定の API の偽物（`httpx.MockTransport` の受け手）。

    入出力は shuhei1101/project-index の develop の `f36ba69` の IF-22〜IF-32 に沿う。

    `docs` は配信元 → リビジョン（`None` は既定）→ 文書の並び、
    `details` は（配信元・パス）→ 文書の取得に足す値（`markdown`・`failure`・`document`）、
    `unreadable` は配信元 → YAML として読めないファイル（文書の取得の `conversionError`）、
    `responses` は（メソッド・パス）→（ステータス・本文）の上書き。
    """

    configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    docs: dict[str, dict[str | None, list[dict[str, Any]]]] = field(default_factory=dict)
    unreadable: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    details: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    decisions: dict[str, dict[str, int]] = field(default_factory=dict)
    decision_texts: dict[tuple[str, str], str] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    search_results: dict[str, Any] = field(default_factory=dict)
    refs_results: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(
        default_factory=lambda: {"settingsPath": "/pi/settings.yaml", "sources": []}
    )
    responses: dict[tuple[str, str], tuple[int, Any]] = field(default_factory=dict)
    refused: bool = False
    requests: list[httpx.Request] = field(default_factory=list)

    def _not_found(self, missing: str, value: str) -> httpx.Response:
        return httpx.Response(404, json={"missing": missing, "value": value, "detail": ""})

    def _default_ref(self, source: str) -> str:
        return "develop" if self.configs[source]["_git"] else ""

    def _detail(self, source: str, file: str, request: httpx.Request) -> httpx.Response:
        """文書の取得（IF-25）に答える。"""
        ref = request.url.params.get("ref")
        doc_id = request.url.params.get("id")
        found = next(
            (
                item
                for item in self.docs.get(source, {}).get(ref, [])
                if file in (item["path"], item.get("bodyPath"))
                and (doc_id is None or item["id"] == doc_id)
            ),
            None,
        )
        extra = dict(self.details.get((source, file)) or {})
        document = extra.pop("document", None) or found
        broken = next(
            (
                problem
                for problem in self.unreadable.get(source, [])
                if file in (problem["file"], problem["file"].rsplit(".", 1)[0])
            ),
            None,
        )
        if document is None and not extra and broken is None:
            return self._not_found("doc", file)
        failure = extra.get("failure") or broken
        metadata = (
            None
            if document is None
            else {
                key: document[key]
                for key in ("id", "kind", "name", "description", "tags", "visibility")
            }
        )
        return httpx.Response(
            200,
            json={
                "source": source,
                "ref": ref or self._default_ref(source),
                "path": document["path"] if document is not None else file,
                "value": None if document is None or broken is not None else document["value"],
                "schema": None,
                "metadata": metadata,
                "body": None if document is None else document["_body"] or None,
                "bodyPath": None if document is None else document["bodyPath"],
                "markdown": extra.get("markdown"),
                "conversionError": failure,
                "updatedAt": (document or {}).get("_updated") or "2026-11-01T10:00:00+09:00",
            },
        )

    def _source(self, parts: list[str], request: httpx.Request) -> httpx.Response:
        """`/sources/{source}/...` に答える。"""
        source = parts[1]
        if source not in self.configs:
            return self._not_found("source", source)
        ref = request.url.params.get("ref")
        if parts[2] == "config":
            schemas = request.url.params.get("schemas") == "true"
            return httpx.Response(200, json=_config_response(self.configs[source], schemas=schemas))
        if parts[2] == "docs" and len(parts) == 3:
            by_ref = self.docs.get(source, {})
            if ref is not None and ref not in by_ref:
                return self._not_found("ref", ref)
            values = request.url.params.get("values") == "true"
            return httpx.Response(
                200,
                json={
                    "ref": ref or self._default_ref(source),
                    "documents": [list_entry(item, values=values) for item in by_ref.get(ref, [])],
                },
            )
        if parts[2] == "docs":
            return self._detail(source, "/".join(parts[3:]), request)
        if parts[2] == "decisions" and len(parts) == 3:
            counts = self.decisions.get(source, {})
            return httpx.Response(
                200,
                json={
                    "decisions": [{"id": key, "folders": value} for key, value in counts.items()]
                },
            )
        if parts[2] == "decisions":
            text = self.decision_texts.get((source, parts[3]))
            if text is None:
                return self._not_found("doc", parts[3])
            return httpx.Response(200, json={"id": parts[3], "folder": "/talks", "body": text})
        if parts[2] == "search":
            return httpx.Response(200, json=self.search_results)
        if self.refs_results:
            return httpx.Response(200, json=self.refs_results)
        git = self.configs[source]["_git"]
        return httpx.Response(
            200,
            json={
                "git": git,
                "defaultRef": self._default_ref(source),
                "branches": [],
                "tags": [],
                "commits": [],
            },
        )

    def _settings(self, request: httpx.Request) -> httpx.Response:
        """端末の設定の API（IF-30〜IF-32）に答える。"""
        if request.method == "POST":
            return httpx.Response(201, json={"result": "added", "same": None, "sources": []})
        if request.method == "PUT":
            rows = json.loads(request.content)["sources"]
            self.settings = {
                **self.settings,
                "sources": [
                    {
                        "id": row.get("id"),
                        "config": row["config"]
                        if isinstance(row["config"], list)
                        else [row["config"]],
                        "enabled": row.get("enabled", True),
                        "scope": {
                            "read": row.get("scope", {}).get("read", []),
                            "write": row.get("scope", {}).get("write"),
                        },
                        "outsideRead": row.get("outside_read", True),
                        "status": "serving" if row.get("enabled", True) else "disabled",
                        "errors": [],
                        "configVersion": None,
                    }
                    for row in rows
                ],
            }
            return httpx.Response(
                200,
                json={
                    "sources": [
                        {"id": item["id"], "status": item["status"]}
                        for item in self.settings["sources"]
                    ]
                },
            )
        return httpx.Response(200, json=self.settings)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.refused:
            raise httpx.ConnectError("refused", request=request)
        path = unquote(request.url.path)
        override = self.responses.get((request.method, path))
        if override is not None:
            status, body = override
            if isinstance(body, str):
                return httpx.Response(status, text=body)
            return httpx.Response(status, json=body)
        parts = path.strip("/").split("/")
        if parts == ["sources"]:
            return httpx.Response(200, json={"sources": self.sources})
        if parts == ["settings", "sources"]:
            return self._settings(request)
        return self._source(parts, request)


@pytest.fixture
def fake_index() -> FakeIndex:
    """project-index の偽物を返す。"""
    return FakeIndex()


@pytest.fixture
def make_client(fake_index: FakeIndex) -> Callable[..., ProjectIndexClient]:
    """偽物の project-index を `httpx.MockTransport` で呼ぶ project-indexの呼び出しを作る関数を返す。"""

    def _make(*, timeout: float = 45) -> ProjectIndexClient:
        return ProjectIndexClient(
            "http://127.0.0.1:8786",
            timeout=timeout,
            transport=httpx.MockTransport(fake_index.handle),
        )

    return _make


@pytest.fixture
def make_terminal_config(tmp_path: Path) -> Callable[..., TerminalConfig]:
    """端末の設定を作る関数を返す。"""

    def _make(**overrides: Any) -> TerminalConfig:
        state_dir = overrides.pop("state_dir", tmp_path / "state")
        values: dict[str, Any] = {
            "file": tmp_path / "settings.yaml",
            "version": "2",
            "clone": tmp_path / "clone",
            "state_dir": state_dir,
            "log_dir": state_dir / "logs",
        }
        values.update(overrides)
        return TerminalConfig(**values)

    return _make


@pytest.fixture
def make_handlers(
    tmp_path: Path,
    make_terminal_config: Callable[..., TerminalConfig],
    make_client: Callable[..., ProjectIndexClient],
) -> Callable[..., Any]:
    """偽物の project-index を呼ぶ配線済みの関数を作る関数を返す（指定した部品だけ差し替える）。"""
    import dataclasses

    from dev_docs.features.convert.service import ConvertService
    from dev_docs.features.lifecycle.control import RestartControl
    from dev_docs.features.view.columns import ColumnSettings
    from dev_docs.main import Handlers

    def _make(**overrides: Any) -> Handlers:
        values: dict[str, Any] = {item.name: None for item in dataclasses.fields(Handlers)}
        values.update(
            {
                "terminal": make_terminal_config(),
                "project_index": make_client(),
                "converter": ConvertService(),
                "columns": ColumnSettings(tmp_path / "columns"),
                "restart": RestartControl(),
            }
        )
        values.update(overrides)
        return Handlers(**values)

    return _make


@pytest.fixture
def bundled_prompts() -> Any:
    """同梱したプロンプトの YAML を、サーバーが描画する全ての ID で読んだ一式を返す。"""
    from dev_docs.features.prompt_doc.runtime import DEFAULT_PROMPTS_DIR, load_prompts
    from dev_docs.server.mcp.result import mcp_prompt_ids

    return load_prompts(DEFAULT_PROMPTS_DIR, required=mcp_prompt_ids())


@pytest.fixture
def make_mcp_handlers(
    make_handlers: Callable[..., Any], bundled_prompts: Any
) -> Callable[..., Any]:
    """同梱したプロンプトの一式を持たせた配線済みの関数を作る関数を返す。"""

    def _make(**overrides: Any) -> Any:
        return make_handlers(**{"prompts": bundled_prompts, **overrides})

    return _make


@pytest.fixture
def make_document() -> Callable[..., IndexedDocument]:
    """文書を作る関数を返す。"""

    def _make(**overrides: Any) -> IndexedDocument:
        values: dict[str, Any] = {
            "id": "doc-1",
            "kind": "rules",
            "source_id": "sample",
            "path": "rules/doc-1.yaml",
            "record_index": None,
            "data": {"id": "doc-1", "name": "文書 1"},
            "body": "id: doc-1\nname: 文書 1\n",
            "body_path": None,
            "metadata": {"id": "doc-1", "name": "文書 1"},
            "version": "9d0e11",
            "updated": None,
        }
        values.update(overrides)
        return IndexedDocument(**values)

    return _make


@pytest.fixture
def make_view() -> Callable[..., SourceView]:
    """配信元の表示の設定を作る関数を返す。"""

    def _make(**overrides: Any) -> SourceView:
        values: dict[str, Any] = {
            "id": "sample",
            "git": True,
            "default_ref": "develop",
            "documents": [DocumentRow(id="rules", paths=["docs/*.yaml"], schema=RULE_SCHEMA)],
        }
        values.update(overrides)
        return SourceView(**values)

    return _make


@pytest.fixture
def write_settings(tmp_path: Path) -> Callable[..., Path]:
    """端末の設定をファイルに書き、そのパスを返す関数を返す（JSON は YAML として読める）。"""

    def _write(**top: Any) -> Path:
        values: dict[str, Any] = {
            "version": "2",
            "clone": str(tmp_path / "clone"),
            "state_dir": str(tmp_path / "state"),
        }
        values.update(top)
        path = tmp_path / "settings.yaml"
        path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def migrations_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """移し替えの手順の置き場所を一時のフォルダに差し替え、そのフォルダを返す。

    絶対パスを手順のフォルダの名前に差し替えると、パッケージのフォルダにつないでも絶対パスが残る。
    """
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
