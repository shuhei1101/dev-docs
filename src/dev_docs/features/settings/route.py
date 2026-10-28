"""設定画面・端末の設定の保存・トップの転送のルート。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dev_docs.features.settings.service import save_sources
from dev_docs.features.settings.types import SettingsSourcesRequest, SettingsSourcesResponse
from dev_docs.features.sources.types import SourceStatus
from dev_docs.features.view.page import PAGE_STATE_ID, embed_json
from dev_docs.server.origin import require_same_origin

if TYPE_CHECKING:
    from dev_docs.main import Handlers

__all__ = ["build_settings_router", "save_sources"]


def _settings_rows(handlers: Handlers) -> list[dict[str, Any]]:
    """`sources[]` の各行に配信元の状態を重ねた値を作る。"""
    statuses: list[SourceStatus] = handlers.registry.statuses()
    by_index = {status.index: status for status in statuses}
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(handlers.terminal.sources):
        status = by_index.get(index)
        row: dict[str, Any] = {
            "id": entry.id,
            "config": list(entry.config),
            "enabled": entry.enabled,
            "scope": {"read": list(entry.scope.read), "write": entry.scope.write},
        }
        if status is not None:
            item = SettingsSourcesResponse.from_statuses([status]).sources[0]
            row["id"] = row["id"] or status.id
            row["status"] = item["status"]
            if "errors" in item:
                row["errors"] = item["errors"]
            if "config_version" in item:
                row["config_version"] = item["config_version"]
        rows.append(row)
    return rows


def build_settings_router(handlers: Handlers) -> APIRouter:
    """トップの転送・設定画面・端末の設定の保存のルートを持つルーターを作る。"""
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/_settings/", status_code=302)

    @router.get("/_settings/", response_class=HTMLResponse)
    def settings_page(request: Request) -> HTMLResponse:
        rows = _settings_rows(handlers)
        config_path = str(handlers.terminal.file)
        context = {
            "config_path": config_path,
            "sources": rows,
            "state_json": embed_json({"config_path": config_path, "sources": rows}),
            "page_state_id": PAGE_STATE_ID,
        }
        response: HTMLResponse = handlers.templates.TemplateResponse(
            request, "settings.html", context
        )
        return response

    @router.put("/_api/settings/sources", dependencies=[Depends(require_same_origin)])
    async def put_sources(body: SettingsSourcesRequest) -> dict[str, Any]:
        statuses = await asyncio.to_thread(
            save_sources,
            body.sources,
            path=handlers.terminal.file,
            reload=handlers.reload_sources,
            lock=handlers.settings_lock,
        )
        return SettingsSourcesResponse.from_statuses(statuses).model_dump()

    return router
