"""管理の MCP の組み立て。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, ValidationError

from dev_docs.features.admin.render import (
    render_check,
    render_reload,
    render_status,
    render_write_nav,
)
from dev_docs.features.admin.service import (
    check_project,
    get_status,
    reload_config,
    try_convert,
    write_nav,
)
from dev_docs.features.admin.types import (
    CheckProjectRequest,
    FormatRequest,
    TryConvertRequest,
    WriteNavRequest,
)
from dev_docs.features.lifecycle.update import update_clone
from dev_docs.server.mcp.result import TOOL_ANNOTATIONS, to_tool_result, tool_error
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

ADMIN_MCP_NAME = "dev-docs-admin"

__all__ = [
    "ADMIN_MCP_NAME",
    "build_admin_mcp",
    "check_project",
    "get_status",
    "reload_config",
    "try_convert",
    "update_clone",
    "write_nav",
]


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
) -> None:
    """要求のモデルを引数に持つツールを 1 つ登録する。"""

    async def tool(**arguments: Any) -> CallToolResult:
        try:
            request = model(**arguments)
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
    """6 つのツールを持つ管理の MCP を作る。"""
    mcp = MCPServer(ADMIN_MCP_NAME)
    _register(
        mcp,
        "status",
        "待ち受けのアドレス・dev-docs のバージョン・端末の設定・配信元ごとの状態を返す。",
        FormatRequest,
        lambda request: get_status(handlers, env=os.environ),
        render_status,
    )
    _register(
        mcp,
        "reload",
        "端末の設定と配信元の設定を読み直し、追加・削除・配信できなくなった配信元を返す。",
        FormatRequest,
        lambda request: reload_config(handlers),
        render_reload,
    )
    _register(
        mcp,
        "restart",
        "応答を返してからサーバーを止め、同じプロセス ID で dev-docs serve を起動し直す。"
        "再起動の後は /mcp でつなぎ直す。",
        NoArguments,
        lambda request: handlers.restart.request(),
    )
    _register(
        mcp,
        "update",
        "dev-docs のクローンで git pull --ff-only と uv sync を行い、"
        "設定の移し替えが要らなければ再起動する。",
        NoArguments,
        lambda request: update_clone(handlers.terminal.clone, control=handlers.restart),
    )
    _register(
        mcp,
        "check_project",
        "配信元の dev-docs.yaml と管理用の YAML・スクリプトを検査し、"
        "違反・設定のバージョンの新旧・索引の同期の件数を返す。端末の設定に無い配信元も検査できる。",
        CheckProjectRequest,
        lambda request: check_project(request, handlers=handlers),
        render_check,
    )
    _register(
        mcp,
        "try_convert",
        "配信元の 1 つのファイルを、配信するときと同じ変換で Markdown にして返す。書き込まない。",
        TryConvertRequest,
        lambda request: try_convert(request, handlers=handlers),
    )
    _register(
        mcp,
        "write_nav",
        "配信元の dev-docs.yaml の nav だけを、タブ・項目の追加・修正・削除で書き換える。"
        "書いた後の nav をスキーマと check_filter で検証し、auto の条件に当たる文書の数を返す。",
        WriteNavRequest,
        lambda request: write_nav(request, handlers=handlers),
        render_write_nav,
    )
    return mcp
