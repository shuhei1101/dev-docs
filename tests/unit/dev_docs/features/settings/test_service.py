from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest

from dev_docs.features.settings.service import save_sources
from dev_docs.features.settings.types import SourceEntry
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexRejectedError

from ...conftest import FakeIndex


def _save(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    entries: list[SourceEntry],
) -> tuple[Any, list[dict[str, Any]]]:
    """保存を依頼し、返った状態と project-index へ送った行を返す。"""
    states = asyncio.run(save_sources(make_client(), entries))
    put = next(request for request in fake_index.requests if request.method == "PUT")
    sent = json.loads(put.content)["sources"]
    return states, sent


def test_save_sources(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """行を送り、状態を返す（正常系）。"""
    # 準備
    # 保存した後の端末の設定の取得で返る行と状態
    fake_index.responses[("GET", "/settings/sources")] = (
        200,
        {
            "settingsPath": "/pi/settings.yaml",
            "sources": [
                {"id": "a", "config": ["/a/project-index.yaml"], "status": "serving", "errors": []},
                {
                    "id": "b",
                    "config": ["/b/project-index.yaml"],
                    "status": "disabled",
                    "errors": [],
                },
            ],
        },
    )
    entries = [
        SourceEntry.model_validate({"id": "a", "config": "/a/project-index.yaml"}),
        SourceEntry.model_validate(
            {"id": "b", "config": ["/b/project-index.yaml"], "scope": {"read": ["/b"]}}
        ),
    ]
    # 実行
    states, sent = _save(fake_index, make_client, entries)
    # 検証
    assert len(sent) == 2
    assert sent[0]["config"] == ["/a/project-index.yaml"]
    assert sent[1]["scope"] == {"read": ["/b"]}
    assert [(state.id, state.status) for state in states] == [
        ("a", "serving"),
        ("b", "disabled"),
    ]


def test_save_sources_when_defaults(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """既定値と同じキーを送らない（正常系）。"""
    # 準備
    entry = SourceEntry.model_validate(
        {
            "id": "a",
            "config": ["/a"],
            "enabled": True,
            "outside_read": True,
            "scope": {"read": []},
        }
    )
    # 実行
    _, sent = _save(fake_index, make_client, [entry])
    # 検証
    assert sent == [{"id": "a", "config": ["/a"]}]


def test_save_sources_when_outside_read_false(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """outside_read: false を送る（正常系）。"""
    # 準備
    entry = SourceEntry.model_validate({"id": "a", "config": ["/a"], "outside_read": False})
    # 実行
    _, sent = _save(fake_index, make_client, [entry])
    # 検証
    assert sent[0]["outside_read"] is False


def test_save_sources_when_rejected(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """project-index が受け付けない（異常系）。"""
    # 準備
    fake_index.responses[("PUT", "/settings/sources")] = (
        422,
        {"errors": [{"path": "sources[0].config", "reason": "無い"}]},
    )
    entry = SourceEntry.model_validate({"id": "a", "config": ["/a"]})
    # 実行・検証
    with pytest.raises(ProjectIndexRejectedError):
        asyncio.run(save_sources(make_client(), [entry]))
