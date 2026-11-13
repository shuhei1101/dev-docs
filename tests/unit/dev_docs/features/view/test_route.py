from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.view.columns import ColumnSettings
from dev_docs.features.view.route import build_view_router
from dev_docs.server.error_handlers import register_error_handlers

from ...conftest import FakeIndex, config_json, doc_json

COLUMNS_BODY = {"table": "rules:items", "hidden": ["a"]}


@pytest.fixture
def sample_index(fake_index: FakeIndex) -> FakeIndex:
    """配信元 sample（`docs/a.yaml`・`docs/b.yaml`）と Git 管理外の notes を置いた偽物を返す。"""
    fake_index.configs["sample"] = config_json("sample")
    fake_index.docs["sample"] = {
        None: [doc_json("a", "docs/a.yaml", name="A"), doc_json("b", "docs/b.yaml", name="B")]
    }
    fake_index.configs["notes"] = config_json("notes", git=False)
    fake_index.refs_results = {"git": False, "branches": [], "tags": [], "commits": []}
    return fake_index


def _client(handlers: Any) -> TestClient:
    """画面のルーターと例外の変換を載せたアプリのテスト用のクライアントを作る。"""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_view_router(handlers))
    return TestClient(app)


def test_build_view_router_when_document(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """文書の取得（正常系）。"""
    # 準備
    client = _client(make_handlers())
    # 実行
    response = client.get("/_api/sources/sample/docs")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["path"] == "docs/a"
    assert "# A" in body["markdown"]
    assert body["tabs"][0]["active"] is True
    assert "updatedAt" in body
    assert body["tableKeys"] == []
    assert not any("_" in key for key in body)


def test_build_view_router_when_document_missing(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """無い文書（異常系）。"""
    # 準備
    client = _client(make_handlers())
    # 実行
    response = client.get("/_api/sources/sample/docs/no-such-doc")
    # 検証
    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert (body["missing"], body["value"]) == ("doc", "no-such-doc")


def test_build_view_router_when_search(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """画面の検索（正常系）。"""
    # 準備
    sample_index.search_results = {
        "totalCount": 1,
        "items": [
            {
                "path": "docs/a",
                "id": "a",
                "filePath": "docs/a.yaml",
                "name": "A",
                "snippets": ["foo"],
            }
        ],
    }
    client = _client(make_handlers())
    # 実行
    response = client.get("/_api/sources/sample/search", params={"q": "foo"})
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["totalCount"] == 1
    assert body["items"][0]["path"] == "docs/a"


def test_build_view_router_when_query_too_long(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """長すぎる語（異常系）。"""
    # 準備
    client = _client(make_handlers())
    # 実行
    response = client.get("/_api/sources/sample/search", params={"q": "x" * 201})
    # 検証
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")


def test_build_view_router_when_refs(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """Git 管理外のリビジョンの一覧（正常系）。"""
    # 準備
    client = _client(make_handlers())
    # 実行
    response = client.get("/_api/sources/notes/refs")
    # 検証
    assert response.status_code == 200
    assert response.json()["git"] is False


def test_build_view_router_when_columns(
    sample_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """列の設定の保存（正常系）。"""
    # 準備
    client = _client(make_handlers())
    # 実行
    saved = client.put(
        "/_api/sources/sample/columns",
        json=COLUMNS_BODY,
        headers={"Sec-Fetch-Site": "same-origin"},
    )
    document = client.get("/_api/sources/sample/docs")
    # 検証
    assert saved.status_code == 200
    assert document.json()["columns"] == {"rules:items": ["a"]}


def test_build_view_router_when_cross_origin(
    sample_index: FakeIndex, make_handlers: Callable[..., Any], tmp_path: Path
) -> None:
    """別のオリジン（異常系）。"""
    # 準備
    columns_dir = tmp_path / "cross-columns"
    client = _client(make_handlers(columns=ColumnSettings(columns_dir)))
    # 実行
    response = client.put(
        "/_api/sources/sample/columns",
        json=COLUMNS_BODY,
        headers={"Origin": "http://evil.example"},
    )
    # 検証
    assert response.status_code == 403
    assert not (columns_dir / "sample.json").exists()


def test_build_view_router_when_project_index_unreachable(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    client = _client(make_handlers())
    # 実行
    responses = [
        client.get("/_api/sources/sample/docs"),
        client.get("/_api/sources/sample/search", params={"q": "x"}),
        client.get("/_api/sources/sample/refs"),
    ]
    # 検証
    assert [response.status_code for response in responses] == [503, 503, 503]
    assert [sorted(response.json()["projectIndex"]) for response in responses] == [
        ["address", "reason"]
    ] * 3
