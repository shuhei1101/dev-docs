"""SessionStart のフックが文脈に入れる文の組み立てと、返し済みの記録の削除。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dev_docs.features.access.service import available_sources
from dev_docs.features.access.types import SourceAccess
from dev_docs.features.admin.service import version_state
from dev_docs.features.documents.store import check_sync
from dev_docs.features.seen.types import SessionKey
from dev_docs.features.session_context.types import (
    CONTEXT_MAX_CHARS,
    FORGET_REASONS,
    SESSION_USAGE,
    SETUP_GUIDE,
    ContextSource,
    SessionContextRequest,
    SessionContextResponse,
)
from dev_docs.features.settings.query import SETTINGS_VERSION
from dev_docs.features.sources.types import SOURCE_CONFIG_VERSION

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

CONTEXT_HEADER = "dev-docs の文書の MCP（dev-docs）で、次の配信元を使えます。"
ACCESS_LABELS = {"write": "読み書き", "read": "読み取りだけ"}
TERMINAL_LABEL = "端末の設定"


def build_session_context(
    request: SessionContextRequest, *, handlers: Handlers
) -> SessionContextResponse:
    """作業場所から使える配信元と警告を集めて文脈の文を作る。"""
    # `/clear`・圧縮の後は、その会話の返し済みの記録を削除する
    forgotten = False
    key = SessionKey.of(request.session_id, request.agent_id)
    if request.reason in FORGET_REASONS and key is not None:
        removed = handlers.seen.forget(key)
        forgotten = True
        logger.info("返し済みの記録を削除した（%s・%s 件）", request.session_id, removed)
    available = available_sources(request.cwd, registry=handlers.registry)
    sources = [
        ContextSource(id=item.source_id, access="read_write" if item.access == "write" else "read")
        for item in available
    ]
    # 使える配信元が無いときは、登録の案内だけを返す
    if not available:
        return SessionContextResponse(
            context=SETUP_GUIDE, sources=sources, warnings=[], forgotten=forgotten
        )
    warnings = _collect_warnings(available, handlers=handlers)
    return SessionContextResponse(
        context=_context_text(available, warnings),
        sources=sources,
        warnings=warnings,
        forgotten=forgotten,
    )


def _collect_warnings(available: list[SourceAccess], *, handlers: Handlers) -> list[str]:
    """使える配信元の同期のずれ・古い設定と、配信していない配信元を警告の文にする。"""
    warnings: list[str] = []
    old_sources: list[str] = []
    for item in available:
        source = handlers.registry.get(item.source_id)
        report = check_sync(handlers.store, source)
        for label, values in (
            ("ref の列の欠け", report.missing_refs),
            ("管理用の YAML に無いファイル", report.unindexed_files),
            ("ファイルが無い行", report.missing_body_files),
        ):
            if values:
                warnings.append(
                    f"{item.source_id}: {label}が {len(values)} 件あります"
                    "（check_project で確かめられます）"
                )
        if version_state(source.config.version, SOURCE_CONFIG_VERSION) == "old":
            old_sources.append(
                _old_version(item.source_id, source.config.version, SOURCE_CONFIG_VERSION)
            )
    warnings.extend(old_sources)
    # 端末の設定のバージョンが古い
    if version_state(handlers.terminal.version, SETTINGS_VERSION) == "old":
        warnings.append(_old_version(TERMINAL_LABEL, handlers.terminal.version, SETTINGS_VERSION))
    # 検証で外した配信元（使える配信元かによらない）
    for status in handlers.registry.statuses():
        if status.status == "not_served" and status.errors:
            first = status.errors[0]
            warnings.append(
                f"{status.id}: 配信していません（{first.path}: {first.rule}）。"
                "check_project で確かめられます"
            )
    return warnings


def _old_version(label: str, mine: str, current: str) -> str:
    """設定のバージョンが古いことを知らせる文を作る。"""
    return (
        f"{label}: 設定のバージョンが古い（{mine}・読める {current}）。"
        "dev-docs migrate で移し替えます"
    )


def _source_line(item: SourceAccess, *, with_description: bool) -> str:
    """配信元 1 つの行を作る。"""
    line = f"- {item.source_id}（{ACCESS_LABELS[item.access]}）"
    if with_description and item.description:
        line += f": {item.description}"
    return line


def _compose(lines: list[str], warnings: list[str]) -> str:
    """見出し・配信元の行・使い方・警告をつなぐ。"""
    parts = [CONTEXT_HEADER, *lines, SESSION_USAGE]
    if warnings:
        parts.extend(["注意:", *(f"- {warning}" for warning in warnings)])
    return "\n".join(parts)


def _context_text(available: list[SourceAccess], warnings: list[str]) -> str:
    """配信元の行・使い方・警告を `CONTEXT_MAX_CHARS` 字以内の文にする。"""
    text = _compose([_source_line(item, with_description=True) for item in available], warnings)
    if len(text) <= CONTEXT_MAX_CHARS:
        return text
    # 超えるときは、配信元の説明を省く
    lines = [_source_line(item, with_description=False) for item in available]
    text = _compose(lines, warnings)
    # それでも超えるときは、収まるまで配信元の行を末尾から減らして残りの件数を添える
    kept = len(lines)
    while len(text) > CONTEXT_MAX_CHARS and kept > 0:
        kept -= 1
        text = _compose([*lines[:kept], f"- ほか {len(lines) - kept} 件"], warnings)
    return text
