"""画面のルート・文書の MCP・管理の MCP・静的ファイルを 1 つのアプリにまとめる。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from dev_docs.main import Handlers

DOCS_MCP_PATH = "/mcp"
ADMIN_MCP_PATH = "/_admin/mcp"
STATIC_PATH = "/_static"


def build_app(handlers: Handlers) -> FastAPI:
    """画面のルート・文書の MCP・管理の MCP・静的ファイルを 1 つの FastAPI のアプリにまとめる。"""
    raise NotImplementedError
