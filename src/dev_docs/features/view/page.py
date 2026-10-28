"""文書の画面とエラーの画面の描画。"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse

from dev_docs.features.access.types import Target
from dev_docs.features.convert.types import Converted, ConvertFailure
from dev_docs.features.documents.types import Document
from dev_docs.features.history.query import resolve_ref
from dev_docs.features.sources.types import ServedSource
from dev_docs.features.view.nav import build_nav, first_page
from dev_docs.features.view.paths import (
    find_page,
    page_path,
    parse_screen_path,
    screen_target,
)
from dev_docs.features.view.types import NavGroup, NavTab, PageState, ScreenPath
from dev_docs.shared.errors import (
    DevDocsError,
    DocumentNotFoundError,
    RefNotFoundError,
    SourceNotServedError,
    UnknownSourceError,
)

if TYPE_CHECKING:
    from dev_docs.main import Handlers

MDMARK_URL = "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.js"
MDMARK_CSS_URL = "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.css"
PAGE_STATE_ID = "page-state"
SHORT_COMMIT = 7
SETTINGS_URL = "/_settings/"
JST = timezone(timedelta(hours=9), "JST")
FAILURE_NEXT = "スクリプトを修正して保存すると、次に開いたときに変換し直します。同じ配信元の他の文書は読めます。"


def embed_json(value: Any) -> str:
    """`<script type="application/json">` に埋め込める JSON の文字列にする。"""
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_page_state(
    source: ServedSource | None,
    screen: ScreenPath | None,
    *,
    handlers: Handlers,
    doc_page: str | None,
    converted: Converted | None,
    diff: dict[str, str] | None,
) -> PageState:
    """画面のスクリプトへ埋め込む値を作る。"""
    menu = [
        {
            "id": item.id,
            "title": item.config.name,
            "note": "読み書き" if item.is_git else "Git 管理外",
        }
        for item in handlers.registry.served()
    ]
    if source is None:
        return PageState(sources=menu)
    default_ref = source.config.default_ref if source.is_git else None
    ref_in_url = screen.ref if screen is not None and source.is_git else None
    return PageState(
        source_id=source.id,
        sources=menu,
        git=source.is_git,
        ref=ref_in_url or default_ref,
        ref_in_url=ref_in_url,
        default_ref=default_ref,
        doc_page=doc_page,
        diff=diff,
        github_repository=source.config.github_repository,
        issue_labels=list(source.config.github_issue_labels),
        table_keys=list(converted.table_keys) if converted is not None else [],
        hidden_columns=handlers.columns.get(source.id),
    )


def _short(commit: str) -> str:
    """commit を短くする。"""
    return commit[:SHORT_COMMIT]


def _iso(moment: datetime | None) -> str:
    """日時を ISO 8601 の文字列にする（無ければ空）。"""
    return moment.isoformat() if moment is not None else ""


def _pages(group: NavGroup) -> list[str]:
    """サイドバーの順に、文書のページのパスを並べる。"""
    pages = [link.page for link in group.links]
    for child in group.groups:
        pages.extend(_pages(child))
    return pages


def _tab_of(tabs: list[NavTab], page: str | None) -> int:
    """開いた文書を含むタブの位置を返す（無ければ先頭）。"""
    if page is not None:
        for index, tab in enumerate(tabs):
            if page in _pages(tab.sidebar):
                return index
    return 0


def _diff_source(
    target: Target, document: Document, diff_ref: str, handlers: Handlers
) -> tuple[str, dict[str, str]]:
    """`?diff=` のリビジョンの同じ文書を変換した Markdown と、画面の状態の `diff` を作る。"""
    source = target.source
    assert source.repo_root is not None  # noqa: S101
    previous = resolve_ref(
        source.repo_root, diff_ref, date_base=source.config.default_ref, argument="diff"
    )
    old_target = Target(source, target.base, previous.commit, None, "read")
    found = {d.id: d for d in handlers.store.load(old_target).documents}.get(document.id)
    markdown = handlers.converter.convert(old_target, found).markdown if found is not None else ""
    current_commit = target.ref or ""
    current_date = ""
    if current_commit:
        current = resolve_ref(source.repo_root, current_commit, date_base=source.config.default_ref)
        current_date = _iso(current.date)
    diff = {
        "ref": diff_ref,
        "commit": _short(previous.commit),
        "date": _iso(previous.date),
        "current_commit": _short(current_commit),
        "current_date": current_date,
    }
    return markdown, diff


def _failure_rows(failure: ConvertFailure) -> list[dict[str, str]]:
    """変換の失敗を、エラーの囲みの行（`{label, value}`）にする。"""
    rows = [{"label": "種類", "value": failure.kind}]
    if failure.script is not None:
        rows.append({"label": "スクリプト", "value": f"`{failure.script}`"})
    elif failure.file is not None:
        rows.append({"label": "ファイル", "value": f"`{failure.file}`"})
        if failure.line is not None:
            rows.append({"label": "場所", "value": f"{failure.line} 行 {failure.column or 1} 列"})
    if failure.reason == "timeout":
        cause = f"制限時間（{failure.detail}）を超えたため、スクリプトを止めました。"
    else:
        cause = failure.detail
    rows.append({"label": "原因", "value": cause})
    return rows


def _first_heading(markdown: str, fallback: str) -> str:
    """変換した Markdown の最初の見出しを返す（無ければ代わりの名前）。"""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _updated(document: Document) -> tuple[str, str]:
    """更新日時を ISO 8601 と `MM/DD HH:mm JST` の文字列にする（無ければ空）。"""
    if document.updated is None:
        return "", ""
    moment = document.updated if document.updated.tzinfo else document.updated.astimezone()
    return moment.isoformat(), moment.astimezone(JST).strftime("%m/%d %H:%M JST")


def render_doc_view(
    request: Request, screen: ScreenPath, *, handlers: Handlers, diff_ref: str | None
) -> HTMLResponse:
    """文書の画面の HTML を作る。"""
    target, _ = screen_target(screen.source_id, screen.ref, registry=handlers.registry)
    source = target.source
    documents = handlers.store.load(target).documents
    tabs = build_nav(source, documents)
    page = screen.page
    document: Document | None = None
    empty_tab = 0
    if page:
        document = find_page(documents, page)
        if document is None:
            raise DocumentNotFoundError(
                message=f"文書がありません: {page}",
                missing=[page],
                next_steps=["画面のサイドバーから文書を選んでください"],
            )
    else:
        # タブを指定したときはそのタブの最初の文書、無ければ文書のある一番左のタブ
        wanted = request.query_params.get("tab")
        order = (
            [int(wanted)]
            if wanted and wanted.isdigit() and int(wanted) < len(tabs)
            else range(len(tabs))
        )
        for index in order:
            first = first_page(tabs[index])
            if first is not None:
                page = first
                document = find_page(documents, first)
                break
        else:
            if wanted and wanted.isdigit() and int(wanted) < len(tabs):
                empty_tab = int(wanted)
    converted = handlers.converter.convert(target, document) if document is not None else None
    diff_markdown: str | None = None
    diff: dict[str, str] | None = None
    if document is not None and diff_ref and source.is_git:
        diff_markdown, diff = _diff_source(target, document, diff_ref, handlers)
    doc_page = page_path(document) if document is not None else None
    state = build_page_state(
        source, screen, handlers=handlers, doc_page=doc_page, converted=converted, diff=diff
    )
    current_tab = _tab_of(tabs, doc_page) if document is not None else empty_tab
    base_path = f"/{source.id}" + (f"@{screen.ref}" if screen.ref else "")
    tab_hrefs = []
    for index, tab in enumerate(tabs):
        first = first_page(tab)
        tab_hrefs.append(f"{base_path}/{quote(first)}" if first else f"{base_path}/?tab={index}")
    updated_iso, updated_text = _updated(document) if document is not None else ("", "")
    table = source.table(document.kind) if document is not None else None
    title = (document.metadata.get("name") or document.id) if document else ""
    context: dict[str, Any] = {
        "source": source,
        "screen": screen,
        "tabs": tabs,
        "current_tab": current_tab,
        "doc": document,
        "doc_title": title,
        "heading": _first_heading(converted.markdown, title) if converted is not None else title,
        "kind_title": (table.title or table.id) if table is not None else "",
        "updated_iso": updated_iso,
        "updated_text": updated_text,
        "revision": _short(target.ref) if target.ref and screen.ref else "",
        "doc_href": f"{base_path}/{quote(doc_page)}" if doc_page else f"{base_path}/",
        "tab_hrefs": tab_hrefs,
        "failure_rows": _failure_rows(converted.failure) if converted and converted.failure else [],
        "failure_next": FAILURE_NEXT,
        "converted": converted,
        "diff_markdown": diff_markdown,
        "state": state,
        "state_json": embed_json(dataclasses.asdict(state)),
        "base_path": base_path,
        "mdmark_url": MDMARK_URL,
        "mdmark_css_url": MDMARK_CSS_URL,
        "page_state_id": PAGE_STATE_ID,
    }
    response: HTMLResponse = handlers.templates.TemplateResponse(request, "doc_view.html", context)
    return response


def _missing_rows(error: DevDocsError, screen: ScreenPath) -> list[dict[str, str]]:
    """見つからなかったものの行（`{label, value}`）を作る。"""
    if isinstance(error, UnknownSourceError):
        return [{"label": "配信元", "value": f"`{error.source_id}` は配信していません。"}]
    if isinstance(error, SourceNotServedError):
        if error.disabled:
            reason = "`enabled` が `false` です。"
        else:
            detail = "、".join(f"`{item.path}`: {item.rule}" for item in error.violations)
            reason = (
                f"起動時の検証で外しました（{detail}）。"
                if detail
                else "起動時の検証で外しました。"
            )
        return [
            {"label": "配信元", "value": f"`{screen.source_id}` は配信していません。"},
            {"label": "理由", "value": reason},
        ]
    if isinstance(error, RefNotFoundError):
        return [
            {"label": "配信元", "value": screen.source_id},
            {
                "label": "リビジョン",
                "value": f"`{error.value}` を解決できませんでした。"
                "ブランチ・タグ・commit のどれにも当たりません。",
            },
        ]
    if isinstance(error, DocumentNotFoundError):
        missing = error.missing[0] if error.missing else screen.page
        return [
            {"label": "配信元", "value": screen.source_id},
            {"label": "文書", "value": f"`{missing}` はありません。"},
        ]
    return [{"label": "エラー", "value": f"{error.name}: {error.message}"}]


def render_error_page(request: Request, error: DevDocsError, *, handlers: Handlers) -> HTMLResponse:
    """画面の GET の `DevDocsError` を見つからない画面の HTML にする。"""
    path = request.url.path.lstrip("/")
    source_part, _, rest = path.partition("/")
    screen = parse_screen_path(source_part, rest)
    served = {item.id: item for item in handlers.registry.served()}
    source = served.get(screen.source_id)
    links = [(item.id, f"/{item.id}/") for item in served.values()]
    links.append(("設定", SETTINGS_URL))
    state = build_page_state(
        source,
        screen if source else None,
        handlers=handlers,
        doc_page=None,
        converted=None,
        diff=None,
    )
    context: dict[str, Any] = {
        "missing_rows": _missing_rows(error, screen),
        "links": links,
        "state": state,
        "state_json": embed_json(dataclasses.asdict(state)),
        "page_state_id": PAGE_STATE_ID,
    }
    response: HTMLResponse = handlers.templates.TemplateResponse(request, "not_found.html", context)
    response.status_code = error.status
    return response
