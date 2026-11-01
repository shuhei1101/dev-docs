"""SessionStart のフックが文脈に入れる文の描画と、返し済みの記録の削除。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dev_docs.features.access.service import available_sources
from dev_docs.features.access.types import SourceAccess
from dev_docs.features.admin.service import version_state
from dev_docs.features.documents.store import check_sync
from dev_docs.features.prompt_doc.runtime import PromptSet
from dev_docs.features.seen.types import SessionKey
from dev_docs.features.session_context.types import (
    CONTEXT_MAX_CHARS,
    FORGET_REASONS,
    SESSION_CONTEXT_PROMPT_ID,
    ContextSource,
    SessionContextRequest,
    SessionContextResponse,
)
from dev_docs.features.settings.query import SETTINGS_VERSION
from dev_docs.features.sources.types import SOURCE_CONFIG_VERSION
from dev_docs.features.view.nav import nav_warnings

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

TERMINAL_LABEL = "端末の設定"


def build_session_context(
    request: SessionContextRequest, *, handlers: Handlers
) -> SessionContextResponse:
    """作業場所から使える配信元と警告を集めて文脈の文を描画する。"""
    # `/clear`・圧縮の後は、その会話の返し済みの記録を削除する
    forgotten = False
    key = SessionKey.of(request.session_id, request.agent_id)
    if request.reason in FORGET_REASONS and key is not None:
        removed = handlers.seen.forget(key)
        forgotten = True
        logger.info("返し済みの記録を削除した（%s・%s 件）", request.session_id, removed)
    # 配信元を読み込んでいる間は、読み込みを待たずに読み込み中の案内を返す
    if handlers.registry.loading:
        return SessionContextResponse(
            context=_context_text([], [], prompts=handlers.prompts, loading=True),
            sources=[],
            warnings=[],
            forgotten=forgotten,
            loading=True,
        )
    available = available_sources(request.cwd, registry=handlers.registry)
    sources = [
        ContextSource(id=item.source_id, access="read_write" if item.access == "write" else "read")
        for item in available
    ]
    warnings = _collect_warnings(available, handlers=handlers) if available else []
    return SessionContextResponse(
        context=_context_text(available, warnings, prompts=handlers.prompts),
        sources=sources,
        warnings=warnings,
        forgotten=forgotten,
    )


def _collect_warnings(available: list[SourceAccess], *, handlers: Handlers) -> list[str]:
    """使える配信元の同期のずれ・古い設定と、配信していない配信元を警告の文にする。"""
    warnings: list[str] = []
    old_sources: list[str] = []
    config_warnings: list[str] = []
    for item in available:
        source = handlers.registry.get(item.source_id)
        report = check_sync(handlers.store, source)
        for label, values in (
            ("metadata の列の欠け", report.missing_refs),
            ("管理用の YAML に無いファイル", report.unindexed_files),
            ("ファイルが無い行", report.missing_body_files),
            ("どの文書にも当たらない関連", report.unresolved_related),
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
        if report.alias_violations:
            config_warnings.append(
                f"{item.source_id}: エイリアスのキーの違反が {len(report.alias_violations)} 件"
                "あります（check_project で確かめられます）"
            )
        config_warnings.extend(
            f"{item.source_id}: {warning.path}: {warning.rule}"
            for warning in nav_warnings(handlers.store, source)
        )
    warnings.extend(old_sources)
    # 端末の設定のバージョンが古い
    if version_state(handlers.terminal.version, SETTINGS_VERSION) == "old":
        warnings.append(_old_version(TERMINAL_LABEL, handlers.terminal.version, SETTINGS_VERSION))
    warnings.extend(config_warnings)
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


def _render(
    sources: list[dict[str, str | None]],
    *,
    omitted: int,
    warnings: list[str],
    prompts: PromptSet,
    loading: bool,
) -> str:
    """配信元・省いた件数・警告・読み込み中かを渡して文脈の文のプロンプトを描画する。"""
    return prompts.render(
        SESSION_CONTEXT_PROMPT_ID,
        {"sources": sources, "omitted": omitted, "warnings": warnings, "loading": loading},
    )


def _context_text(
    available: list[SourceAccess],
    warnings: list[str],
    *,
    prompts: PromptSet,
    loading: bool = False,
) -> str:
    """配信元と警告をプロンプトの YAML で `CONTEXT_MAX_CHARS` 字以内の文に描画する。"""
    sources: list[dict[str, str | None]] = [
        {
            "id": item.source_id,
            "access": "read_write" if item.access == "write" else "read",
            "description": item.description,
        }
        for item in available
    ]
    text = _render(sources, omitted=0, warnings=warnings, prompts=prompts, loading=loading)
    if len(text) <= CONTEXT_MAX_CHARS:
        return text
    # 超えるときは、配信元の説明を省く
    sources = [{**source, "description": None} for source in sources]
    text = _render(sources, omitted=0, warnings=warnings, prompts=prompts, loading=loading)
    # それでも超えるときは、収まるまで配信元を末尾から減らして残りの件数を添える
    kept = len(sources)
    while len(text) > CONTEXT_MAX_CHARS and kept > 0:
        kept -= 1
        text = _render(
            sources[:kept],
            omitted=len(sources) - kept,
            warnings=warnings,
            prompts=prompts,
            loading=loading,
        )
    return text
