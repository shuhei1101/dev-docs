from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from dev_docs.server.app import build_app, route_operation_id


def _endpoint() -> None:
    """ルートの例に使う何もしない関数。"""


def _screen_dir(tmp_path: Path) -> Path:
    """index.html だけを置いた画面のビルドのフォルダを返す。"""
    screen_dir = tmp_path / "screen"
    screen_dir.mkdir()
    (screen_dir / "index.html").write_text("<html>screen</html>", encoding="utf-8")
    return screen_dir


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
    assert client.post("/_admin/session-context", json={"cwd": "/"}).status_code == 200


def test_build_app_when_openapi(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any], tmp_path: Path
) -> None:
    """OpenAPI の画面を出さない（正常系）。"""
    # 準備
    screen_dir = _screen_dir(tmp_path)
    client = TestClient(build_app(_handlers(make_handlers, make_registry), screen_dir=screen_dir))
    # 実行
    docs = client.get("/docs")
    schema = client.get("/_api/openapi.json")
    # 検証
    paths = schema.json()["paths"]
    operation_ids = [
        operation["operationId"] for item in paths.values() for operation in item.values()
    ]
    assert docs.status_code == 200
    assert docs.text == "<html>screen</html>"
    assert all(path.startswith("/_api/") for path in paths)
    assert sorted(operation_ids) == sorted(
        [
            "view-get_document_default",
            "view-get_document",
            "view-search_page",
            "view-list_refs",
            "view-put_columns",
            "settings-get_settings_sources",
            "settings-put_settings_sources",
        ]
    )
    assert len(operation_ids) == len(set(operation_ids))


def test_build_app_when_screen(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any], tmp_path: Path
) -> None:
    """API と MCP を画面の配信より先に当てる（正常系）。"""
    # 準備
    client = TestClient(
        build_app(_handlers(make_handlers, make_registry), screen_dir=_screen_dir(tmp_path))
    )
    # 実行
    screen = client.get("/default/a.md")
    api = client.get("/_api/sources/none/docs")
    # 検証
    assert screen.status_code == 200
    assert screen.text == "<html>screen</html>"
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/problem+json")


def test_route_operation_id() -> None:
    """タグと名前を結ぶ（正常系）。"""
    # 準備
    route = APIRoute("/x", _endpoint, tags=["view"], name="get_document")
    # 実行
    result = route_operation_id(route)
    # 検証
    assert result == "view-get_document"


def test_route_operation_id_when_no_tag() -> None:
    """タグが無いと名前だけ（正常系）。"""
    # 準備
    route = APIRoute("/x", _endpoint, tags=[], name="x")
    # 実行
    result = route_operation_id(route)
    # 検証
    assert result == "x"
