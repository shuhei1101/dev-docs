"""文書の MCP の組み立て。"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel, Field, ValidationError

from dev_docs.features.changes.render import render_changes_markdown
from dev_docs.features.changes.service import list_changes
from dev_docs.features.changes.types import ChangesRequest
from dev_docs.features.describe.render import render_describe_markdown
from dev_docs.features.describe.service import describe
from dev_docs.features.describe.types import DescribeRequest
from dev_docs.features.related.render import render_related_markdown
from dev_docs.features.related.service import trace_related
from dev_docs.features.related.types import RelatedRequest
from dev_docs.features.search.render import render_search_markdown
from dev_docs.features.search.service import search_docs
from dev_docs.features.search.terms import list_match_words, render_match_words_markdown
from dev_docs.features.search.types import MatchWordsRequest, SearchRequest
from dev_docs.features.write.service import delete_docs, write_docs
from dev_docs.features.write.types import DeleteRequest, WriteRequest
from dev_docs.server.mcp.result import (
    DOCS_INSTRUCTIONS_PROMPT_ID,
    TOOL_ANNOTATIONS,
    to_tool_result,
    tool_error,
    tool_prompt_id,
)
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

DOCS_MCP_NAME = "dev-docs"

__all__ = [
    "DOCS_MCP_NAME",
    "build_docs_mcp",
    "delete_docs",
    "describe",
    "list_changes",
    "list_match_words",
    "search_docs",
    "trace_related",
    "write_docs",
]


def _signature(model: type[BaseModel]) -> inspect.Signature:
    """要求のモデルのフィールドを、ツールの入力のスキーマにするキーワード引数にする。"""
    parameters = []
    for name, info in model.model_fields.items():
        annotation: Any = info.annotation
        extras: dict[str, Any] = {}
        if info.alias:
            # `from` は Python の予約語なので、属性は `from_`・入力のスキーマでは `from` にする
            extras["validation_alias"] = info.alias
        if info.description:
            # 要求のモデルのフィールドの説明を、入力のスキーマの項目の説明に出す
            extras["description"] = info.description
        if extras:
            annotation = Annotated[annotation, Field(**extras)]
        default = (
            inspect.Parameter.empty
            if info.is_required()
            else info.get_default(call_default_factory=True)
        )
        parameters.append(
            inspect.Parameter(
                name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation
            )
        )
    return inspect.Signature(parameters, return_annotation=CallToolResult)


def _register(
    mcp: MCPServer,
    name: str,
    description: str,
    model: type[BaseModel],
    call: Callable[[Any], Any],
    render: Callable[[Any, Any], str] | None,
    *,
    wait_loaded: Callable[[], Awaitable[None]],
) -> None:
    """要求のモデルを引数に持つツールを 1 つ登録する（呼ぶ前に配信元の読み込みを待つ）。"""

    async def tool(**arguments: Any) -> CallToolResult:
        try:
            request = model(**arguments)
            await wait_loaded()
            result = await asyncio.to_thread(call, request)
            fmt: Literal["markdown", "json"] = getattr(request, "format", "json")
            return to_tool_result(
                result, fmt, (lambda value: render(value, request)) if render else None
            )
        except (DevDocsError, ValidationError) as error:
            return tool_error(error)
        except Exception:
            logger.exception("ツールの処理に失敗した（%s）", name)
            raise

    tool.__signature__ = _signature(model)  # type: ignore[attr-defined]
    tool.__doc__ = description
    mcp.tool(name=name, description=description, annotations=TOOL_ANNOTATIONS[name])(tool)


def build_docs_mcp(handlers: Handlers) -> MCPServer:
    """7 つのツールを持つ文書の MCP を作る。"""
    mcp = MCPServer(
        DOCS_MCP_NAME, instructions=handlers.prompts.render(DOCS_INSTRUCTIONS_PROMPT_ID)
    )
    timeout = handlers.terminal.script_timeout_sec
    register = functools.partial(_register, wait_loaded=lambda: handlers.registry.wait_loaded())

    register(
        mcp,
        "search_docs",
        handlers.prompts.render(tool_prompt_id("docs", "search_docs")),
        SearchRequest,
        lambda request: search_docs(
            request,
            registry=handlers.registry,
            store=handlers.store,
            checker=handlers.checker,
            seen=handlers.seen,
        ),
        lambda result, request: render_search_markdown(result, source_label=result.source_label),
    )
    register(
        mcp,
        "describe",
        handlers.prompts.render(tool_prompt_id("docs", "describe")),
        DescribeRequest,
        lambda request: describe(request, registry=handlers.registry, store=handlers.store),
        lambda result, request: render_describe_markdown(result),
    )
    register(
        mcp,
        "list_changes",
        handlers.prompts.render(tool_prompt_id("docs", "list_changes")),
        ChangesRequest,
        lambda request: list_changes(
            request, registry=handlers.registry, store=handlers.store, seen=handlers.seen
        ),
        lambda result, request: render_changes_markdown(
            result, source_label=str(request.source or "作業中の配信元")
        ),
    )
    register(
        mcp,
        "trace_related",
        handlers.prompts.render(tool_prompt_id("docs", "trace_related")),
        RelatedRequest,
        lambda request: trace_related(
            request, registry=handlers.registry, store=handlers.store, seen=handlers.seen
        ),
        lambda result, request: render_related_markdown(result),
    )
    register(
        mcp,
        "write_docs",
        handlers.prompts.render(tool_prompt_id("docs", "write_docs")),
        WriteRequest,
        lambda request: write_docs(
            request,
            registry=handlers.registry,
            store=handlers.store,
            checker=handlers.checker,
            seen=handlers.seen,
            locks=handlers.locks,
            timeout_sec=timeout,
        ),
        None,
    )
    register(
        mcp,
        "delete_docs",
        handlers.prompts.render(tool_prompt_id("docs", "delete_docs")),
        DeleteRequest,
        lambda request: delete_docs(
            request,
            registry=handlers.registry,
            store=handlers.store,
            checker=handlers.checker,
            locks=handlers.locks,
            timeout_sec=timeout,
        ),
        None,
    )
    register(
        mcp,
        "list_match_words",
        handlers.prompts.render(tool_prompt_id("docs", "list_match_words")),
        MatchWordsRequest,
        lambda request: list_match_words(request, registry=handlers.registry, store=handlers.store),
        lambda result, request: render_match_words_markdown(result),
    )
    return mcp
