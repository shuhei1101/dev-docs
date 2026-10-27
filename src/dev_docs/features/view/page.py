"""文書の画面とエラーの画面の描画。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import HTMLResponse

from dev_docs.features.convert.types import Converted
from dev_docs.features.sources.types import ServedSource
from dev_docs.features.view.types import PageState, ScreenPath
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

MDMARK_URL = "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.js"
MDMARK_CSS_URL = "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.css"
PAGE_STATE_ID = "page-state"


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
    raise NotImplementedError


def render_doc_view(
    request: Request, screen: ScreenPath, *, handlers: Handlers, diff_ref: str | None
) -> HTMLResponse:
    """文書の画面の HTML を作る。"""
    raise NotImplementedError


def render_error_page(request: Request, error: DevDocsError, *, handlers: Handlers) -> HTMLResponse:
    """画面の GET の `DevDocsError` を見つからない画面の HTML にする。"""
    raise NotImplementedError
