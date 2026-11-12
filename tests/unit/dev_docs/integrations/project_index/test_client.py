from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import (
    DocumentNotFoundError,
    ProjectIndexRejectedError,
    ProjectIndexResponseError,
    ProjectIndexUnreachableError,
    RefNotFoundError,
    SourceNotServedError,
    UnknownSourceError,
)

from ...conftest import FakeIndex, config_json, doc_json


def _client(
    handler: Callable[[httpx.Request], httpx.Response], *, timeout: float = 45
) -> ProjectIndexClient:
    """受け手の関数を `httpx.MockTransport` で呼ぶ project-indexの呼び出しを作る。"""
    return ProjectIndexClient(
        "http://127.0.0.1:8786/", timeout=timeout, transport=httpx.MockTransport(handler)
    )


def test_request_when_refused() -> None:
    """接続を断られる（異常系）。"""

    # 準備
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(refuse)
    # 実行
    with pytest.raises(ProjectIndexUnreachableError) as caught:
        asyncio.run(client.request("GET", "/sources"))
    # 検証
    assert caught.value.address == "http://127.0.0.1:8786"
    assert caught.value.reason == "接続を拒否されました（Connection refused）"


def test_request_when_timeout() -> None:
    """制限時間を超える（異常系）。"""

    # 準備
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = _client(slow, timeout=45)
    # 実行
    with pytest.raises(ProjectIndexUnreachableError) as caught:
        asyncio.run(client.request("GET", "/sources"))
    # 検証
    assert caught.value.reason == "45 秒以内に応答がありませんでした"


def test_request_when_total_timeout() -> None:
    """要求全体の上限（異常系）。"""

    # 準備
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(3):
            await asyncio.sleep(0.15)
            yield b"x"

    def streaming(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=chunks())

    client = _client(streaming, timeout=0.2)
    # 実行
    with pytest.raises(ProjectIndexUnreachableError) as caught:
        asyncio.run(client.request("GET", "/sources"))
    # 検証
    assert caught.value.reason == "0.2 秒以内に応答がありませんでした"


@pytest.mark.parametrize(
    ("missing", "expected", "field", "value"),
    [
        pytest.param("source", UnknownSourceError, lambda e: e.source_id, "x", id="source"),
        pytest.param(
            "not_served", SourceNotServedError, lambda e: len(e.violations), 1, id="not_served"
        ),
        pytest.param(
            "ref", RefNotFoundError, lambda e: (e.argument, e.value), ("ref", "x"), id="ref"
        ),
        pytest.param("doc", DocumentNotFoundError, lambda e: e.missing, ["x"], id="doc"),
    ],
)
def test_request_when_not_found(
    missing: str, expected: type[Exception], field: Callable[[Any], Any], value: Any
) -> None:
    """404 の missing ごとの例外と、例外に入れる値（異常系）。"""
    # 準備
    body = {
        "missing": missing,
        "value": "x",
        "errors": [{"path": "documents[0].paths", "reason": "必須のキーが無い"}],
    }
    client = _client(lambda request: httpx.Response(404, json=body))
    # 実行
    with pytest.raises(expected) as caught:
        asyncio.run(client.request("GET", "/sources/x/docs"))
    # 検証
    assert field(caught.value) == value


def test_request_when_unexpected_status() -> None:
    """想定しないステータス（異常系）。"""
    # 準備
    client = _client(lambda request: httpx.Response(500, text="e" * 300))
    # 実行
    with pytest.raises(ProjectIndexResponseError) as caught:
        asyncio.run(client.request("GET", "/sources"))
    # 検証
    assert caught.value.status_code == 500
    assert caught.value.summary == "e" * 200


def test_list_sources(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """状態の読み替え（正常系）。"""
    # 準備
    fake_index.sources = [
        {"id": "sample", "status": "serving"},
        {
            "id": "broken",
            "status": "not_served",
            "errors": [{"path": "documents[0].paths", "reason": "必須のキーが無い"}],
        },
    ]
    # 実行
    states = asyncio.run(make_client().list_sources())
    # 検証
    assert [state.id for state in states] == ["sample", "broken"]
    assert len(states[1].errors) == 1
    assert states[1].errors[0].rule == "必須のキーが無い"


def test_source_view(fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]) -> None:
    """画面の構成と文書の行（正常系）。"""
    # 準備
    nav = {"tabs": [{"title": "規約", "items": [{"auto": {"document": "rules"}}]}]}
    fake_index.configs["sample"] = config_json(
        nav=nav,
        documents=[
            {"id": "rules", "paths": ["docs/*.yaml"], "schema": {}},
            {"id": "notes", "paths": ["notes/files.yaml"], "schema": {}, "records": "files"},
        ],
    )
    # 実行
    view = asyncio.run(make_client().source_view("sample"))
    # 検証
    assert view.nav == nav
    assert len(view.documents) == 2
    assert view.documents[1].records == "files"


def test_list_documents(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """ref を渡す（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    fake_index.docs["sample"] = {
        "8b1d4e0": [doc_json("a", "docs/a.yaml"), doc_json("b", "docs/b.yaml")]
    }
    # 実行
    listed = asyncio.run(make_client().list_documents("sample", ref="8b1d4e0"))
    # 検証
    assert fake_index.requests[-1].url.params["ref"] == "8b1d4e0"
    assert listed.ref == "8b1d4e0"
    assert [document.id for document in listed.documents] == ["a", "b"]


def test_document_when_failure(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """変換の失敗（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    fake_index.details[("sample", "docs/a.yaml")] = {
        "failure": {
            "reason": "timeout",
            "kind": "rules",
            "script": "python conv.py",
            "detail": "30 秒",
        }
    }
    # 実行
    detail = asyncio.run(make_client().document("sample", "docs/a.yaml"))
    # 検証
    assert detail.markdown is None
    assert detail.failure is not None
    assert detail.failure.reason == "timeout"


def test_document_when_record(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """管理用の YAML の行の要素を選ぶ（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    fake_index.docs["sample"] = {
        None: [
            doc_json("n-0", "notes/files.yaml", record_index=0),
            doc_json("n-1", "notes/files.yaml", record_index=1),
        ]
    }
    # 実行
    detail = asyncio.run(make_client().document("sample", "notes/files.yaml", document_id="n-1"))
    # 検証
    assert fake_index.requests[-1].url.params["id"] == "n-1"
    assert detail.document is not None
    assert detail.document.id == "n-1"


def test_decisions(fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]) -> None:
    """リンクにできる ID（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    fake_index.decisions["sample"] = {"D-1": 1, "D-2": 2}
    # 実行
    index = asyncio.run(make_client().decisions("sample"))
    # 検証
    assert index.linkable == {"D-1"}


def test_decision_when_ambiguous(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """2 つのフォルダにある（異常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    # 実行・検証
    with pytest.raises(DocumentNotFoundError):
        asyncio.run(make_client().decision("sample", "D-2"))


def test_search(fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]) -> None:
    """クエリを渡す（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json()
    fake_index.search_results = {
        "totalCount": 3,
        "items": [{"id": "a", "path": "docs/a.yaml", "name": "A", "snippets": ["…ページング…"]}],
    }
    # 実行
    hits = asyncio.run(make_client().search("sample", "ページング", limit=5))
    # 検証
    params = fake_index.requests[-1].url.params
    assert params["q"] == "ページング"
    assert params["limit"] == "5"
    assert hits.total_count == 3
    assert hits.items[0].path == "docs/a.yaml"


def test_refs_when_not_git(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """Git 管理外（正常系）。"""
    # 準備
    fake_index.configs["notes"] = config_json("notes", git=False)
    fake_index.refs_results = {"git": False, "defaultRef": ""}
    # 実行
    refs = asyncio.run(make_client().refs("notes", commits=20))
    # 検証
    assert refs.git is False
    assert refs.branches == []
    assert refs.commits == []


def test_settings_sources(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """行と状態（正常系）。"""
    # 準備
    fake_index.settings = {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            {
                "row": {"id": "a", "config": ["/a/project-index.yaml"]},
                "id": "a",
                "status": "serving",
            },
            {
                "row": {"id": "b", "config": ["/b/project-index.yaml"]},
                "id": "b",
                "status": "disabled",
            },
        ],
    }
    # 実行
    view = asyncio.run(make_client().settings_sources())
    # 検証
    assert len(view.rows) == 2
    assert len(view.states) == 2
    assert view.settings_path == "/pi/settings.yaml"


def test_put_settings_sources_when_rejected(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """スキーマに通らない（異常系）。"""
    # 準備
    fake_index.responses[("PUT", "/settings/sources")] = (
        422,
        {"errors": [{"path": "sources[0].config", "reason": "必須"}]},
    )
    # 実行
    with pytest.raises(ProjectIndexRejectedError) as caught:
        asyncio.run(make_client().put_settings_sources([{"id": "a"}]))
    # 検証
    assert [item.path for item in caught.value.violations] == ["sources[0].config"]


def test_add_settings_source_when_conflict(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """同じ id の行がある（正常系）。"""
    # 準備
    fake_index.responses[("POST", "/settings/sources")] = (409, {"same": True})
    # 実行
    result = asyncio.run(
        make_client().add_settings_source({"id": "a", "config": ["/a/project-index.yaml"]})
    )
    # 検証
    assert result.added is False
    assert result.same is True
