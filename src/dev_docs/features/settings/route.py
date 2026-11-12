"""端末の設定の取得・保存のルート。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from dev_docs.features.settings.service import save_sources
from dev_docs.features.settings.types import (
    SettingsSourceRow,
    SettingsSourcesRequest,
    SettingsSourcesResponse,
    SettingsSourcesView,
    SourceScope,
)
from dev_docs.integrations.project_index.types import SourceState
from dev_docs.server.origin import require_same_origin

if TYPE_CHECKING:
    from dev_docs.main import Handlers

__all__ = ["build_settings_router", "save_sources"]


def _row(raw: dict[str, Any], state: SourceState | None, item: Any) -> SettingsSourceRow:
    """project-index の行に状態を重ねる。"""
    config = raw.get("config") or []
    scope = raw.get("scope") or {}
    return SettingsSourceRow(
        id=state.id if state is not None and state.id is not None else raw.get("id"),
        config=[config] if isinstance(config, str) else list(config),
        enabled=bool(raw.get("enabled", True)),
        scope=SourceScope(read=list(scope.get("read") or []), write=scope.get("write")),
        status=state.status if state is not None else "pending_reload",
        errors=item.errors if item is not None else [],
        config_version=item.config_version if item is not None else None,
        outside_read=bool(raw.get("outside_read", True)),
    )


def build_settings_router(handlers: Handlers) -> APIRouter:
    """端末の設定の取得・保存のルートを持つルーターを作る。"""
    router = APIRouter(tags=["settings"])

    @router.get("/_api/settings/sources", name="get_settings_sources")
    async def get_sources() -> SettingsSourcesView:
        view = await handlers.project_index.settings_sources()
        items = SettingsSourcesResponse.from_states(view.states).sources
        rows = [
            _row(
                raw,
                view.states[index] if index < len(view.states) else None,
                items[index] if index < len(items) else None,
            )
            for index, raw in enumerate(view.rows)
        ]
        return SettingsSourcesView(settings_path=view.settings_path, sources=rows)

    @router.put(
        "/_api/settings/sources",
        name="put_settings_sources",
        dependencies=[Depends(require_same_origin)],
    )
    async def put_sources(body: SettingsSourcesRequest) -> SettingsSourcesResponse:
        states = await save_sources(handlers.project_index, body.sources)
        return SettingsSourcesResponse.from_states(states)

    return router
