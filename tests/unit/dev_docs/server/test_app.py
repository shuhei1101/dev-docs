from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from dev_docs.server import app as app_module
from dev_docs.server.app import build_app, route_operation_id

from ..conftest import FakeIndex

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

    middleware = app_module.SlashlessMcpPathMiddleware(next_app, paths=("/_admin/mcp",))
    asyncio.run(middleware(scope, _noop_receive, _noop_send))
    return received


def test_build_app(make_mcp_handlers: Callable[..., Any]) -> None:
    """管理の MCP と画面の API を持つ（正常系）。"""
    # 準備
    app = build_app(make_mcp_handlers())
    client = TestClient(app)
    # 実行
    response = client.get("/_api/openapi.json")
    # 検証
    mounted = [getattr(route, "path", "") for route in app.routes]
    assert response.status_code == 200
    assert "/_api/sources/{source}/docs" in response.json()["paths"]
    assert "/_api/settings/sources" in response.json()["paths"]
    assert "/_admin/mcp" in mounted
    assert "/mcp" not in mounted
    assert "/_admin/session-start" not in mounted


def test_build_app_when_openapi(make_mcp_handlers: Callable[..., Any], tmp_path: Path) -> None:
    """OpenAPI の画面を出さない（正常系）。"""
    # 準備
    client = TestClient(build_app(make_mcp_handlers(), screen_dir=_screen_dir(tmp_path)))
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
    fake_index: FakeIndex, make_mcp_handlers: Callable[..., Any], tmp_path: Path
) -> None:
    """API を画面の配信より先に当てる（正常系）。"""
    # 準備
    client = TestClient(build_app(make_mcp_handlers(), screen_dir=_screen_dir(tmp_path)))
    # 実行
    screen = client.get("/default/a.md")
    api = client.get("/_api/sources/none/docs")
    # 検証
    assert screen.status_code == 200
    assert screen.text == "<html>screen</html>"
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/problem+json")


def test_build_app_when_mcp_without_slash(
    make_mcp_handlers: Callable[..., Any], tmp_path: Path
) -> None:
    """スラッシュ無しの管理の MCP のパスへの POST を MCP が受ける（正常系）。"""
    # 準備
    app = build_app(make_mcp_handlers(), screen_dir=_screen_dir(tmp_path))
    with TestClient(app, base_url=LOCAL_BASE_URL, follow_redirects=False) as client:
        # 実行
        admin = client.post("/_admin/mcp", headers=MCP_HEADERS, json=INITIALIZE)
        docs = client.post("/mcp", headers=MCP_HEADERS, json=INITIALIZE)
        other = client.get("/_admin/mcpx")
    # 検証
    assert admin.status_code == 200
    assert "serverInfo" in admin.json()["result"]
    assert docs.status_code == 404
    assert docs.headers["content-type"].startswith("application/problem+json")
    assert other.status_code == 404


def test_slashless_mcp_path_middleware() -> None:
    """スラッシュ無しの MCP のパスにスラッシュを補う（正常系）。"""
    # 準備
    admin_scope = {"type": "http", "path": "/_admin/mcp", "raw_path": b"/_admin/mcp"}
    # 実行
    admin = _pass_through(admin_scope)
    # 検証
    assert admin[0]["path"] == "/_admin/mcp/"
    assert admin[0]["raw_path"] == b"/_admin/mcp/"
    assert admin_scope["path"] == "/_admin/mcp"


@pytest.mark.parametrize(
    "scope",
    [
        pytest.param(
            {"type": "http", "path": "/_admin/mcp/", "raw_path": b"/_admin/mcp/"}, id="with_slash"
        ),
        pytest.param(
            {"type": "http", "path": "/_admin/mcpx", "raw_path": b"/_admin/mcpx"}, id="prefix"
        ),
        pytest.param({"type": "http", "path": "/mcp", "raw_path": b"/mcp"}, id="removed"),
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
