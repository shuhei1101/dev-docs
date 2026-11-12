"""管理の MCP の `status` の中身。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

from dev_docs.features.admin.types import (
    ProjectIndexState,
    ServerStatus,
    SourceState,
    TerminalState,
    VersionState,
)
from dev_docs.features.settings.query import SETTINGS_VERSION, listen_port
from dev_docs.integrations.project_index.types import SourceState as IndexSourceState
from dev_docs.shared.errors import ProjectIndexResponseError, ProjectIndexUnreachableError
from dev_docs.shared.version import RUNNING_VERSION

if TYPE_CHECKING:
    from dev_docs.main import Handlers


def version_state(mine: str, current: str) -> VersionState:
    """設定のバージョンを dev-docs が読めるバージョンと比べる。"""
    left, right = int(mine), int(current)
    if left == right:
        return "current"
    return "old" if left < right else "newer"


def _state(state: IndexSourceState) -> SourceState:
    """project-index の状態を `status` の行にする。"""
    errors = [f"{item.path}: {item.rule}" for item in state.errors]
    return SourceState(id=state.id, status=state.status, errors=errors)


async def get_status(handlers: Handlers, *, env: Mapping[str, str]) -> ServerStatus:
    """待ち受けのアドレス・バージョン・project-index への接続と配信元ごとの状態を返す。"""
    terminal = handlers.terminal
    port = listen_port(terminal, env)
    client = handlers.project_index
    sources: list[SourceState] = []
    error: str | None = None
    try:
        sources = [_state(state) for state in await client.list_sources()]
    except ProjectIndexUnreachableError as unreachable:
        error = unreachable.reason
    except ProjectIndexResponseError as unexpected:
        error = unexpected.summary or unexpected.message
    return ServerStatus(
        address=f"http://{terminal.bind}:{port}/",
        version=RUNNING_VERSION,
        pid=os.getpid(),
        terminal=TerminalState(
            file=str(terminal.file),
            version_state=version_state(terminal.version, SETTINGS_VERSION),
        ),
        project_index=ProjectIndexState(
            address=client.address, reachable=error is None, error=error
        ),
        sources=sources,
        leftover_sources=list(terminal.leftover_sources),
    )
