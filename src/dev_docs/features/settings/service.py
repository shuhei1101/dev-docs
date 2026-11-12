"""設定画面からの `sources[]` の保存の依頼。"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from dev_docs.features.settings.types import SourceEntry
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.integrations.project_index.types import SourceState

logger = logging.getLogger(__name__)


def _to_row(entry: SourceEntry) -> dict[str, Any]:
    """既定値と同じキーを送信しない `sources[]` の 1 行にする。"""
    row: dict[str, Any] = {}
    if entry.id is not None:
        row["id"] = entry.id
    row["config"] = list(entry.config)
    if not entry.enabled:
        row["enabled"] = False
    if not entry.outside_read:
        row["outside_read"] = False
    scope: dict[str, Any] = {}
    if entry.scope.read:
        scope["read"] = list(entry.scope.read)
    if entry.scope.write is not None:
        scope["write"] = list(entry.scope.write)
    if scope:
        row["scope"] = scope
    return row


async def save_sources(
    client: ProjectIndexClient, sources: Sequence[SourceEntry]
) -> list[SourceState]:
    """送信された `sources[]` を project-index の端末の設定の API へ指定し、再読み込みした後の状態を返却する。"""
    view = await client.put_settings_sources([_to_row(entry) for entry in sources])
    logger.info("端末の設定の sources の保存を依頼した（%s 行）", len(sources))
    return view.states
