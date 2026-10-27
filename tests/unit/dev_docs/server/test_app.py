from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from dev_docs.server.app import build_app


def _handlers(make_handlers: Callable[..., Any], make_registry: Callable[..., Any]) -> Any:
    """配信元が空の配線済みの関数を作る。"""
    return make_handlers(registry=make_registry(), templates=Jinja2Templates(directory="."))


def test_build_app(make_handlers: Callable[..., Any], make_registry: Callable[..., Any]) -> None:
    """入口を全て持つ（正常系）。"""
    # 準備
    app = build_app(_handlers(make_handlers, make_registry))
    client = TestClient(app, follow_redirects=False)
    # 実行
    response = client.get("/")
    # 検証
    mounted = [getattr(route, "path", "") for route in app.routes]
    assert response.status_code == 302
    assert response.headers["location"] == "/_settings/"
    assert "/mcp" in mounted
    assert "/_admin/mcp" in mounted
    assert "/_static" in mounted


def test_build_app_when_openapi(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any]
) -> None:
    """OpenAPI の画面を出さない（正常系）。"""
    # 準備
    client = TestClient(build_app(_handlers(make_handlers, make_registry)))
    # 実行
    response = client.get("/docs")
    # 検証
    assert response.status_code == 404
    assert "UnknownSourceError" in response.text
