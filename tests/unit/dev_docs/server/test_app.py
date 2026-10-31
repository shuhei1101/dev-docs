from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from dev_docs.server import app as app_module
from dev_docs.server.app import build_app, route_operation_id

LOCAL_BASE_URL = "http://127.0.0.1:8781"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "unit-test", "version": "0"},
    },
}


def _endpoint() -> None:
    """ルートの例に使う何もしない関数。"""


def _screen_dir(tmp_path: Path) -> Path:
    """index.html だけを置いた画面のビルドのフォルダを返す。"""
    screen_dir = tmp_path / "screen"
    screen_dir.mkdir()
    (screen_dir / "index.html").write_text("<html>screen</html>", encoding="utf-8")
    return screen_dir


async def _noop_receive() -> Message:
    """何も届かない ASGI の receive。"""
    return {"type": "http.request"}


async def _noop_send(message: Message) -> None:
    """何も送らない ASGI の send。"""


def _pass_through(scope: Scope) -> list[Scope]:
    """スラッシュを補うミドルウェアに scope を渡し、次のアプリが受け取った scope を返す。"""
    received: list[Scope] = []

    async def next_app(scope: Scope, receive: Receive, send: Send) -> None:
        received.append(scope)

    middleware = app_module.SlashlessMcpPathMiddleware(next_app, paths=("/mcp", "/_admin/mcp"))
    asyncio.run(middleware(scope, _noop_receive, _noop_send))
    return received


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


def test_build_app_when_mcp_without_slash(
    make_handlers: Callable[..., Any], make_registry: Callable[..., Any], tmp_path: Path
) -> None:
    """スラッシュ無しの MCP のパスへの POST を画面の配信でなく MCP が受ける（正常系）。"""
    # 準備
    handlers = make_handlers(
        registry=make_registry(), seen=SimpleNamespace(purge_expired=lambda: 0)
    )
    app = build_app(handlers, screen_dir=_screen_dir(tmp_path))
    with TestClient(app, base_url=LOCAL_BASE_URL, follow_redirects=False) as client:
        # 実行
        docs = client.post("/mcp", headers=MCP_HEADERS, json=INITIALIZE)
        admin = client.post("/_admin/mcp", headers=MCP_HEADERS, json=INITIALIZE)
        screen = client.get("/mcpx")
    # 検証
    assert docs.status_code == 200
    assert "serverInfo" in docs.json()["result"]
    assert admin.status_code == 200
    assert "serverInfo" in admin.json()["result"]
    assert screen.status_code == 200
    assert screen.text == "<html>screen</html>"


def test_slashless_mcp_path_middleware() -> None:
    """スラッシュ無しの MCP のパスにスラッシュを補う（正常系）。"""
    # 準備
    docs_scope = {"type": "http", "path": "/mcp", "raw_path": b"/mcp"}
    admin_scope = {"type": "http", "path": "/_admin/mcp", "raw_path": b"/_admin/mcp"}
    # 実行
    docs = _pass_through(docs_scope)
    admin = _pass_through(admin_scope)
    # 検証
    assert docs[0]["path"] == "/mcp/"
    assert docs[0]["raw_path"] == b"/mcp/"
    assert admin[0]["path"] == "/_admin/mcp/"
    assert admin[0]["raw_path"] == b"/_admin/mcp/"
    assert docs_scope["path"] == "/mcp"
    assert admin_scope["path"] == "/_admin/mcp"


@pytest.mark.parametrize(
    "scope",
    [
        pytest.param({"type": "http", "path": "/mcp/", "raw_path": b"/mcp/"}, id="with_slash"),
        pytest.param({"type": "http", "path": "/mcpx", "raw_path": b"/mcpx"}, id="prefix"),
        pytest.param(
            {"type": "http", "path": "/sample/mcp", "raw_path": b"/sample/mcp"}, id="nested"
        ),
        pytest.param({"type": "lifespan"}, id="lifespan"),
    ],
)
def test_slashless_mcp_path_middleware_when_other_path(scope: dict[str, Any]) -> None:
    """他のパスと HTTP でない要求はそのまま渡す（正常系）。"""
    # 実行
    received = _pass_through(scope)
    # 検証
    assert received[0] is scope


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
