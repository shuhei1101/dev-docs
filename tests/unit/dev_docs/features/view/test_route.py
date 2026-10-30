from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.view.route import build_view_router
from dev_docs.server.error_handlers import register_error_handlers


def _client(handlers: Any) -> TestClient:
    """画面のルーターと例外の変換を載せたアプリのテスト用のクライアントを作る。"""
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_view_router(handlers))
    return TestClient(app)


def test_build_view_router_when_document(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """文書の取得（正常系）。"""
    # 準備
    client = _client(make_view_env().handlers)
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
    make_view_env: Callable[..., SimpleNamespace],
) -> None:
    """無い文書（異常系）。"""
    # 準備
    client = _client(make_view_env().handlers)
    # 実行
    response = client.get("/_api/sources/sample/docs/no-such-doc")
    # 検証
    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert body["missing"] == "doc"
    assert body["value"] == "no-such-doc"


def test_build_view_router_when_search(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """画面の検索（正常系）。"""
    # 準備
    env = make_view_env({"docs/a.yaml": "id: a\nname: foo の文書\n"})
    client = _client(env.handlers)
    # 実行
    response = client.get("/_api/sources/sample/search", params={"q": "foo"})
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["totalCount"] == 1
    assert body["items"][0]["path"] == "docs/a"


def test_build_view_router_when_query_too_long(
    make_view_env: Callable[..., SimpleNamespace],
) -> None:
    """長すぎる語（異常系）。"""
    # 準備
    client = _client(make_view_env().handlers)
    # 実行
    response = client.get("/_api/sources/sample/search", params={"q": "x" * 201})
    # 検証
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")


def test_build_view_router_when_refs(
    make_view_env: Callable[..., SimpleNamespace],
) -> None:
    """Git 管理外のリビジョンの一覧（正常系）。"""
    # 準備
    client = _client(make_view_env(is_git=False).handlers)
    # 実行
    response = client.get("/_api/sources/sample/refs")
    # 検証
    assert response.status_code == 200
    assert response.json()["git"] is False


def test_build_view_router_when_columns(make_view_env: Callable[..., SimpleNamespace]) -> None:
    """列の設定の保存（正常系）。"""
    # 準備
    client = _client(make_view_env().handlers)
    # 実行
    saved = client.put(
        "/_api/sources/sample/columns",
        json={"table": "rules:items", "hidden": ["a"]},
        headers={"Sec-Fetch-Site": "same-origin"},
    )
    document = client.get("/_api/sources/sample/docs")
    # 検証
    assert saved.status_code == 200
    assert document.json()["columns"] == {"rules:items": ["a"]}


def test_build_view_router_when_cross_origin(
    make_view_env: Callable[..., SimpleNamespace],
) -> None:
    """別のオリジン（異常系）。"""
    # 準備
    env = make_view_env()
    client = _client(env.handlers)
    # 実行
    response = client.put(
        "/_api/sources/sample/columns",
        json={"table": "rules:items", "hidden": ["a"]},
        headers={"Origin": "http://evil.example"},
    )
    # 検証
    assert response.status_code == 403
    assert not (env.columns_dir / "sample.json").exists()
