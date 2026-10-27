from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from dev_docs.server.mcp.admin import build_admin_mcp


def test_build_admin_mcp(make_handlers: Callable[..., Any]) -> None:
    """ツールが無い（正常系）。"""
    # 準備
    mcp = build_admin_mcp(make_handlers())
    # 実行
    tools = asyncio.run(mcp.list_tools())
    # 検証
    assert tools == []
