"""文書の画面と画面の API のルート。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from dev_docs.main import Handlers

REFS_COMMITS_DEFAULT = 20
REFS_COMMITS_MAX = 100


def build_view_router(handlers: Handlers) -> APIRouter:
    """文書の画面と画面の API のルートを持つルーターを作る。"""
    raise NotImplementedError
