from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from dev_docs.features.admin.service import get_status, version_state

from ...conftest import FakeIndex

REFUSED = "接続を拒否されました（Connection refused）"


def test_get_status(fake_index: FakeIndex, make_handlers: Callable[..., Any]) -> None:
    """project-index の状態を写す（正常系）。"""
    # 準備
    fake_index.sources = [
        {"id": "sample", "status": "serving", "errors": []},
        {
            "id": "broken",
            "status": "not_served",
            "errors": [{"path": "documents[0].paths", "reason": "必須のキーが無い"}],
        },
        {"id": "off", "status": "disabled", "errors": []},
    ]
    handlers = make_handlers()
    # 実行
    result = asyncio.run(get_status(handlers, env={}))
    # 検証
    assert result.address == f"http://127.0.0.1:{handlers.terminal.port}/"
    assert result.project_index.reachable is True
    assert [(state.id, state.status) for state in result.sources] == [
        ("sample", "serving"),
        ("broken", "not_served"),
        ("off", "disabled"),
    ]
    assert result.sources[1].errors == ["documents[0].paths: 必須のキーが無い"]


def test_get_status_when_port_env(make_handlers: Callable[..., Any]) -> None:
    """環境変数のポート（正常系）。"""
    # 実行
    result = asyncio.run(get_status(make_handlers(), env={"DEV_DOCS_PORT": "8799"}))
    # 検証
    assert result.address == "http://127.0.0.1:8799/"


def test_get_status_when_unreachable(
    fake_index: FakeIndex, make_handlers: Callable[..., Any]
) -> None:
    """project-index につながらない（正常系）。"""
    # 準備
    fake_index.refused = True
    # 実行
    result = asyncio.run(get_status(make_handlers(), env={}))
    # 検証
    assert result.project_index.reachable is False
    assert result.project_index.error == REFUSED
    assert result.sources == []


def test_get_status_when_leftover_sources(
    make_handlers: Callable[..., Any], make_terminal_config: Callable[..., Any]
) -> None:
    """端末の設定に残った sources（正常系）。"""
    # 準備
    handlers = make_handlers(terminal=make_terminal_config(leftover_sources=["sample"]))
    # 実行
    result = asyncio.run(get_status(handlers, env={}))
    # 検証
    assert result.leftover_sources == ["sample"]


@pytest.mark.parametrize(
    ("mine", "current", "expected"),
    [
        pytest.param("1", "1", "current", id="same"),
        pytest.param("1", "2", "old", id="older"),
        pytest.param("3", "2", "newer", id="newer"),
    ],
)
def test_version_state(mine: str, current: str, expected: str) -> None:
    """同じ・古い・新しいを分ける（正常系）。"""
    # 実行
    result = version_state(mine, current)
    # 検証
    assert result == expected


def test_version_state_when_not_integer() -> None:
    """整数でない（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="invalid literal"):
        version_state("a", "1")
