"""管理の MCP の組み立て。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

if TYPE_CHECKING:
    from dev_docs.main import Handlers

ADMIN_MCP_NAME = "dev-docs-admin"


def build_admin_mcp(handlers: Handlers) -> MCPServer:
    """ツールを持たない管理の MCP を作る。"""
    return MCPServer(ADMIN_MCP_NAME)
