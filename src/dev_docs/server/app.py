"""画面の API・画面の配信・管理の MCP を 1 つのアプリにまとめる。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.routing import APIRoute

from dev_docs.features.settings.route import build_settings_router
from dev_docs.features.view.route import build_view_router
from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.server.lifespan import build_lifespan
from dev_docs.server.mcp.admin import build_admin_mcp
from dev_docs.server.screen import SCREEN_DIST_DIR, build_screen_router

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from dev_docs.main import Handlers

ADMIN_MCP_PATH = "/_admin/mcp"
OPENAPI_PATH = "/_api/openapi.json"


class SlashlessMcpPathMiddleware:
    """スラッシュ無しの MCP のパスへの要求を、ルーティングの前に末尾にスラッシュを付けたパスへ書き換える。"""

    def __init__(self, app: ASGIApp, *, paths: Iterable[str]) -> None:
        self._app = app
        self._paths = frozenset(paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # マウントは `/_admin/mcp/...` にだけ当たり、`/_admin/mcp` は画面の配信のルートに当たって POST が 405 になる
        if scope["type"] == "http" and scope["path"] in self._paths:
            scope = {
                **scope,
                "path": scope["path"] + "/",
                "raw_path": scope["raw_path"] + b"/",
            }
        await self._app(scope, receive, send)


def route_operation_id(route: APIRoute) -> str:
    """OpenAPI の operationId をルートのタグと名前から作る（`{タグ}-{名前}`）。"""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name


def build_app(handlers: Handlers, *, screen_dir: Path = SCREEN_DIST_DIR) -> FastAPI:
    """画面の API・管理の MCP・画面の配信を 1 つの FastAPI のアプリにまとめる。"""
    admin_mcp = build_admin_mcp(handlers)
    app = FastAPI(
        lifespan=build_lifespan([admin_mcp], project_index=handlers.project_index),
        docs_url=None,
        redoc_url=None,
        openapi_url=OPENAPI_PATH,
        generate_unique_id_function=route_operation_id,
    )
    app.state.handlers = handlers
    register_error_handlers(app)
    app.mount(
        ADMIN_MCP_PATH,
        admin_mcp.streamable_http_app(
            streamable_http_path="/", stateless_http=True, json_response=True
        ),
    )
    app.add_middleware(SlashlessMcpPathMiddleware, paths=(ADMIN_MCP_PATH,))
    app.include_router(build_settings_router(handlers))
    app.include_router(build_view_router(handlers))
    # 全てのパスに当たるため、最後に登録する
    app.include_router(build_screen_router(screen_dir))
    return app
