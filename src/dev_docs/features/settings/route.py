"""設定画面・端末の設定の保存・トップの転送のルート。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from dev_docs.features.settings.service import save_sources

if TYPE_CHECKING:
    from dev_docs.main import Handlers

__all__ = ["build_settings_router", "save_sources"]


def build_settings_router(handlers: Handlers) -> APIRouter:
    """トップの転送・設定画面・端末の設定の保存のルートを持つルーターを作る。"""
    raise NotImplementedError
