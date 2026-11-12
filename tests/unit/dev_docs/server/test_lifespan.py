from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI

from dev_docs.server.lifespan import build_lifespan


def _fake_mcp(name: str, events: list[str]) -> SimpleNamespace:
    """`session_manager.run()` が入った・出たを記録する MCP の偽物を作る。"""

    @asynccontextmanager
    async def run() -> Any:
        events.append(f"{name}.enter")
        yield
        events.append(f"{name}.exit")

    return SimpleNamespace(session_manager=SimpleNamespace(run=run))


def test_build_lifespan() -> None:
    """MCP のセッションの管理を動かし、出るときに project-index の呼び出しを閉じる（正常系）。"""
    # 準備
    events: list[str] = []

    async def aclose() -> None:
        events.append("aclose")

    lifespan = build_lifespan(
        [_fake_mcp("admin", events)],  # type: ignore[list-item]
        project_index=SimpleNamespace(aclose=aclose),  # type: ignore[arg-type]
    )

    async def scenario() -> list[str]:
        async with lifespan(FastAPI()):
            return list(events)

    # 実行
    inside = asyncio.run(scenario())
    # 検証
    assert inside == ["admin.enter"]
    assert events == ["admin.enter", "admin.exit", "aclose"]
