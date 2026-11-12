"""アプリの寿命。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer

from dev_docs.integrations.project_index.client import ProjectIndexClient


def build_lifespan(
    mcps: Sequence[MCPServer], *, project_index: ProjectIndexClient
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """マウントした MCP のセッションの管理を親のアプリの寿命で動かし、止まるときに project-index の呼び出しを閉じる。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            stack.push_async_callback(project_index.aclose)
            # マウントした子のアプリの寿命は動かないので、親で MCP のセッションの管理を動かす
            for mcp in mcps:
                await stack.enter_async_context(mcp.session_manager.run())
            yield

    return lifespan
