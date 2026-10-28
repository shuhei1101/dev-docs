from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from dev_docs.server.app import build_app


def _handlers(make_handlers: Callable[..., Any], make_registry: Callable[..., Any]) -> Any:
    """配信元が空の配線済みの関数を作る。"""
    return make_handlers(registry=make_registry())


def test_build_app(make_handlers: Callable[..., Any], make_registry: Callable[..., Any]) -> None:
    """入口を全て持つ（正常系）。"""
    # 準備
    app = build_app(_handlers(make_handlers, make_registry))
    client = TestClient(app)
    # 実行
    response = client.get("/_api/openapi.json")
    # 検証
    mounted = [getattr(route, "path", "") for route in app.routes]
    assert response.status_code == 200
    assert "/_api/sources/{source}/docs" in response.json()["paths"]
    assert "/_api/settings/sources" in response.json()["paths"]
    assert "/mcp" in mounted
    assert "/_admin/mcp" in mounted


def test_build_app_when_openapi(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any]
) -> None:
    """OpenAPI の画面を出さない（正常系）。"""
    # 準備
    client = TestClient(build_app(_handlers(make_handlers, make_registry)))
    # 実行
    docs = client.get("/docs")
    schema = client.get("/_api/openapi.json")
    # 検証
    paths = schema.json()["paths"]
    operation_ids = [
        operation["operationId"] for item in paths.values() for operation in item.values()
    ]
    assert docs.status_code == 404
    assert all(path.startswith("/_api/") for path in paths)
    assert sorted(operation_ids) == sorted(
        [
            "get_document_default",
            "get_document",
            "search_page",
            "list_refs",
            "put_columns",
            "get_settings_sources",
            "put_settings_sources",
        ]
    )
