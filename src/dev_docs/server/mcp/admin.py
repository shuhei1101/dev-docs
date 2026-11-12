"""管理の MCP の組み立て。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, ValidationError

from dev_docs.features.admin.render import render_status
from dev_docs.features.admin.service import get_status
from dev_docs.features.admin.types import FormatRequest
from dev_docs.features.lifecycle.update import update_clone
from dev_docs.server.mcp.result import (
    TOOL_ANNOTATIONS,
    to_tool_result,
    tool_error,
    tool_prompt_id,
)
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

ADMIN_MCP_NAME = "dev-docs-admin"

__all__ = ["ADMIN_MCP_NAME", "build_admin_mcp", "get_status", "update_clone"]


class NoArguments(BaseModel):
    """引数を持たないツールの引数。"""

    model_config = ConfigDict(extra="forbid")


def _signature(model: type[BaseModel]) -> inspect.Signature:
    """要求のモデルのフィールドを、ツールの入力のスキーマにするキーワード引数にする。"""
    parameters = [
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty
            if info.is_required()
            else info.get_default(call_default_factory=True),
            annotation=info.annotation,
        )
        for name, info in model.model_fields.items()
    ]
    return inspect.Signature(parameters, return_annotation=CallToolResult)


def _register(
    mcp: MCPServer,
    name: str,
    description: str,
    model: type[BaseModel],
    call: Callable[[Any], Any],
    render: Callable[[Any], str] | None = None,
    *,
    awaited: Callable[[Any], Awaitable[Any]] | None = None,
) -> None:
    """要求のモデルを引数に持つツールを 1 つ登録する（`awaited` は await で、`call` はスレッドで呼ぶ）。"""

    async def tool(**arguments: Any) -> CallToolResult:
        try:
            request = model(**arguments)
            if awaited is not None:
                result = await awaited(request)
            else:
                result = await asyncio.to_thread(call, request)
            fmt: Literal["markdown", "json"] = getattr(request, "format", "json")
            return to_tool_result(result, fmt, render)
        except (DevDocsError, ValidationError) as error:
            return tool_error(error)
        except Exception:
            logger.exception("ツールの処理に失敗した（%s）", name)
            raise

    tool.__signature__ = _signature(model)  # type: ignore[attr-defined]
    tool.__doc__ = description
    mcp.tool(name=name, description=description, annotations=TOOL_ANNOTATIONS[name])(tool)


def build_admin_mcp(handlers: Handlers) -> MCPServer:
    """3 つのツールを持つ管理の MCP を作る。"""
    mcp = MCPServer(ADMIN_MCP_NAME)
    _register(
        mcp,
        "status",
        handlers.prompts.render(tool_prompt_id("admin", "status")),
        FormatRequest,
        lambda request: None,
        render_status,
        awaited=lambda request: get_status(handlers, env=os.environ),
    )
    _register(
        mcp,
        "restart",
        handlers.prompts.render(tool_prompt_id("admin", "restart")),
        NoArguments,
        lambda request: handlers.restart.request(),
    )
    _register(
        mcp,
        "update",
        handlers.prompts.render(tool_prompt_id("admin", "update")),
        NoArguments,
        lambda request: update_clone(handlers.terminal.clone, control=handlers.restart),
    )
    return mcp
