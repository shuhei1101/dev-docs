"""端末の設定の取得・保存のルート。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from dev_docs.features.settings.query import load_terminal_config
from dev_docs.features.settings.service import save_sources
from dev_docs.features.settings.types import (
    SettingsSourceRow,
    SettingsSourcesRequest,
    SettingsSourcesResponse,
    SettingsSourcesView,
)
from dev_docs.server.origin import require_same_origin

if TYPE_CHECKING:
    from dev_docs.main import Handlers

__all__ = ["build_settings_router", "save_sources"]


def _settings_view(handlers: Handlers) -> SettingsSourcesView:
    """端末の設定を読み直し、`sources[]` の各行に同じ順の配信元の状態を重ねる。"""
    terminal = load_terminal_config(handlers.terminal.file)
    statuses = handlers.registry.statuses()
    items = {
        status.index: item
        for status, item in zip(
            statuses, SettingsSourcesResponse.from_statuses(statuses).sources, strict=True
        )
    }
    rows: list[SettingsSourceRow] = []
    for index, entry in enumerate(terminal.sources):
        item = items[index]
        rows.append(
            SettingsSourceRow(
                id=item["id"],
                config=list(entry.config),
                enabled=entry.enabled,
                scope=entry.scope,
                status=item["status"],
                errors=item.get("errors", []),
                config_version=item.get("config_version"),
            )
        )
    return SettingsSourcesView(settings_path=str(terminal.file), sources=rows)


def build_settings_router(handlers: Handlers) -> APIRouter:
    """端末の設定の取得・保存のルートを持つルーターを作る。"""
    router = APIRouter()

    @router.get("/_api/settings/sources", operation_id="get_settings_sources")
    async def get_sources() -> SettingsSourcesView:
        return await asyncio.to_thread(_settings_view, handlers)

    @router.put(
        "/_api/settings/sources",
        operation_id="put_settings_sources",
        dependencies=[Depends(require_same_origin)],
    )
    async def put_sources(body: SettingsSourcesRequest) -> SettingsSourcesResponse:
        statuses = await asyncio.to_thread(
            save_sources,
            body.sources,
            path=handlers.terminal.file,
            reload=handlers.reload_sources,
            lock=handlers.settings_lock,
        )
        return SettingsSourcesResponse.from_statuses(statuses)

    return router
