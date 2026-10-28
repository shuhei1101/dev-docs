"""画面のルート・文書の MCP・管理の MCP・静的ファイルを 1 つのアプリにまとめる。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dev_docs.features.settings.route import build_settings_router
from dev_docs.features.view.route import build_view_router
from dev_docs.server.error_handlers import register_error_handlers
from dev_docs.server.lifespan import build_lifespan
from dev_docs.server.mcp.admin import build_admin_mcp
from dev_docs.server.mcp.docs import build_docs_mcp

if TYPE_CHECKING:
    from dev_docs.main import Handlers

DOCS_MCP_PATH = "/mcp"
ADMIN_MCP_PATH = "/_admin/mcp"
STATIC_PATH = "/_static"
STATIC_DIR = Path(__file__).parent / "static"


def build_app(handlers: Handlers) -> FastAPI:
    """画面のルート・文書の MCP・管理の MCP・静的ファイルを 1 つの FastAPI のアプリにまとめる。"""
    docs_mcp = build_docs_mcp(handlers)
    admin_mcp = build_admin_mcp(handlers)
    app = FastAPI(
        lifespan=build_lifespan([docs_mcp, admin_mcp], seen=handlers.seen),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.handlers = handlers
    register_error_handlers(app)
    for path, mcp in ((DOCS_MCP_PATH, docs_mcp), (ADMIN_MCP_PATH, admin_mcp)):
        app.mount(
            path,
            mcp.streamable_http_app(
                streamable_http_path="/", stateless_http=True, json_response=True
            ),
        )
    app.mount(STATIC_PATH, StaticFiles(directory=STATIC_DIR), name="static")
    # 画面の /{source}/... より先に /_settings/・/_api/ を当てる
    app.include_router(build_settings_router(handlers))
    app.include_router(build_view_router(handlers))
    return app
