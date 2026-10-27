"""文書の MCP の組み立て。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from dev_docs.features.changes.service import list_changes
from dev_docs.features.describe.service import describe
from dev_docs.features.related.service import trace_related
from dev_docs.features.search.service import search_docs
from dev_docs.features.write.service import delete_docs, write_docs

if TYPE_CHECKING:
    from dev_docs.main import Handlers

DOCS_MCP_NAME = "dev-docs"

__all__ = [
    "DOCS_MCP_NAME",
    "build_docs_mcp",
    "delete_docs",
    "describe",
    "list_changes",
    "search_docs",
    "trace_related",
    "write_docs",
]


def build_docs_mcp(handlers: Handlers) -> MCPServer:
    """6 つのツールを持つ文書の MCP を作る。"""
    raise NotImplementedError
