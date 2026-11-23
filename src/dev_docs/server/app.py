"""画面の API・画面の配信・管理の MCP を 1 つのアプリにまとめる。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.gzip import GZipMiddleware

from dev_docs.features.metadata.route import build_metadata_router
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
# 画面のAPIの応答の圧縮が適用するパスの頭
API_PATH_PREFIX = "/_api/"
# 応答を圧縮する本文の最小のバイト数（これより小さい本文は gzip のヘッダーの分だけ縮まらないことがある）
GZIP_MINIMUM_SIZE = 500


class SlashlessMcpPathMiddleware:
    """スラッシュ無しの MCP のパスへの要求を、ルーティングの前に末尾にスラッシュを付けたパスへ書き換える。"""

    def __init__(self, app: ASGIApp, *, paths: Iterable[str]) -> None:
        self._app = app
        self._paths = frozenset(paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # マウントは `/_admin/mcp/...` にだけ該当し、`/_admin/mcp` は画面の配信のルートに該当して POST が 405 になる
        if scope["type"] == "http" and scope["path"] in self._paths:
            scope = {
                **scope,
                "path": scope["path"] + "/",
                "raw_path": scope["raw_path"] + b"/",
            }
        await self._app(scope, receive, send)


class ApiGZipMiddleware:
    """画面の API への要求だけ、`Accept-Encoding` に gzip を含むときに応答を gzip で返却する。"""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._gzip = GZipMiddleware(app, minimum_size=GZIP_MINIMUM_SIZE)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 画面の API の HTTP の要求: 圧縮する。管理の MCP・画面の配信・lifespan はそのまま渡す
        if scope["type"] == "http" and scope["path"].startswith(API_PATH_PREFIX):
            await self._gzip(scope, receive, send)
        else:
            await self._app(scope, receive, send)


def route_operation_id(route: APIRoute) -> str:
    """OpenAPI の operationId をルートのタグと名前から作る（`{タグ}-{名前}`）。"""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name


def build_app(
    handlers: Handlers, *, screen_dir: Path = SCREEN_DIST_DIR, mdmark_version: str = "develop"
) -> FastAPI:
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
    app.add_middleware(ApiGZipMiddleware)
    app.include_router(build_settings_router(handlers))
    app.include_router(build_view_router(handlers))
    app.include_router(build_metadata_router(handlers))
    # 全てのパスに該当するため、最後に登録する
    app.include_router(build_screen_router(screen_dir, mdmark_version=mdmark_version))
    return app
