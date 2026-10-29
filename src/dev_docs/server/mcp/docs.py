"""文書の MCP の組み立て。"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
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
from dev_docs.features.search.types import SearchRequest
from dev_docs.features.write.service import delete_docs, write_docs
from dev_docs.features.write.types import DeleteRequest, WriteRequest
from dev_docs.server.mcp.result import TOOL_ANNOTATIONS, to_tool_result, tool_error
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
) -> None:
    """要求のモデルを引数に持つツールを 1 つ登録する。"""

    async def tool(**arguments: Any) -> CallToolResult:
        try:
            request = model(**arguments)
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
    """6 つのツールを持つ文書の MCP を作る。"""
    mcp = MCPServer(DOCS_MCP_NAME)
    timeout = handlers.terminal.script_timeout_sec

    _register(
        mcp,
        "search_docs",
        "条件に当たる文書を、指定した項目・量・順で返す。ID で絞れば取得、view: summary で一覧、"
        "view: count で件数、group_by で集計になる。"
        "op: regex は値の各行に当たる（値全体の先頭・末尾は \\A・\\Z）。"
        "snippets は本文の代わりに、当たった行と前後の行（before・after。省けば context_lines）"
        "を行番号つきで返す。"
        "filter の not は中の条件か束に当たらない文書、op: glob は **・*・? のパターンに当たる。"
        "fields・order_by の @matches は文書ごとの本文の条件に当たった行の数。"
        "sections（Markdown の見出し）・lines（offset・limit）は view: full の本文の一部だけを返す。",
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
    _register(
        mcp,
        "describe",
        "今の作業場所から使える配信元の一覧（引数なし）、配信元の説明書と種類の一覧（source）、"
        "種類のスキーマ（source と kind）を返す。",
        DescribeRequest,
        lambda request: describe(request, registry=handlers.registry, store=handlers.store),
        lambda result, request: render_describe_markdown(result),
    )
    _register(
        mcp,
        "list_changes",
        "2 つのリビジョンの間、またはこの会話で前回読んだ時点からの、文書の変更を返す。"
        "contains は語（regex で正規表現）の出現数が変わった文書と、語が入った・消えた commit を返す"
        "（git log -S と同じくマージ commit は見ない）。",
        ChangesRequest,
        lambda request: list_changes(
            request, registry=handlers.registry, store=handlers.store, seen=handlers.seen
        ),
        lambda result, request: render_changes_markdown(
            result, source_label=str(request.source or "作業中の配信元")
        ),
    )
    _register(
        mcp,
        "trace_related",
        "起点の文書やコードのパスから、related をたどって関連する文書を返す。",
        RelatedRequest,
        lambda request: trace_related(
            request, registry=handlers.registry, store=handlers.store, seen=handlers.seen
        ),
        lambda result, request: render_related_markdown(result),
    )
    _register(
        mcp,
        "write_docs",
        "文書を作る・部分更新する・置き換える。操作を全て当てた後の文書を検査に通し、"
        "通ったときだけ作業ツリーのファイルを書き換える（commit はしない）。"
        "範囲のファイルを作った・消した・改名したら、管理用の YAML の行を修正する。"
        "set・unset・add_to・remove_from・text_edits のキーには共通のキー"
        "（id・name・description・tags・alias_type など）も使え、種類の列名へ読み替えて書く。"
        "対応は describe(source, kind) で見る。",
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
    _register(
        mcp,
        "delete_docs",
        "文書を消す。参照されている文書は on_referenced に従って断るか、参照も外して消す。",
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
    return mcp
