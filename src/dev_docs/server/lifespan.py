"""アプリの寿命。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer

from dev_docs.features.seen.store import SeenStore


def build_lifespan(
    mcps: Sequence[MCPServer], *, seen: SeenStore
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """マウントした MCP のセッションの管理を親のアプリの寿命で動かし、起動時に古い会話の記録を削除する。"""
    raise NotImplementedError
