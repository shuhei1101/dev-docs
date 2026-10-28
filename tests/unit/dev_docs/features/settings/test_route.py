from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dev_docs.features.settings import route as route_module
from dev_docs.features.settings.route import build_settings_router
from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import SourceStatus
from dev_docs.shared.errors import Violation

SETTINGS = (
    'version: "1"\n'
    "clone: /tmp/clone\n"
    "sources:\n"
    "  - id: a\n"
    "    config: /tmp/a/dev-docs.yaml\n"
    "  - id: b\n"
    "    config: /tmp/b/dev-docs.yaml\n"
)


class FakeRegistry(SourceRegistry):
    """決めた状態を返す配信元の一覧の偽物。"""

    def __init__(self, statuses: list[SourceStatus]) -> None:
        super().__init__()
        self._statuses = statuses

    def statuses(self) -> list[SourceStatus]:
        return self._statuses


def test_build_settings_router_when_get(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_handlers: Callable[..., Any],
    make_terminal_config: Callable[..., TerminalConfig],
    make_status: Callable[..., SourceStatus],
) -> None:
    """行に状態を重ねる（正常系）。"""
    # 準備
    write_files(tmp_path, {"settings.yaml": SETTINGS})
    statuses = [
        make_status("a", 0, config=("/tmp/a/dev-docs.yaml",)),
        make_status(
            "b",
            1,
            "not_served",
            config=("/tmp/b/dev-docs.yaml",),
            errors=[Violation(path="documents[0].paths", rule="必須のキーが無い")],
        ),
    ]
    terminal = make_terminal_config(file=tmp_path / "settings.yaml")
    handlers = make_handlers(terminal=terminal, registry=FakeRegistry(statuses))
    app = FastAPI()
    app.include_router(build_settings_router(handlers))
    client = TestClient(app)
    # 実行
    response = client.get("/_api/settings/sources")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["settings_path"] == str(terminal.file)
    assert [row["id"] for row in body["sources"]] == ["a", "b"]
    assert body["sources"][0]["config"] == ["/tmp/a/dev-docs.yaml"]
    assert body["sources"][0]["status"] == "serving"
    assert body["sources"][1]["status"] == "not_served"
    assert body["sources"][1]["errors"] == [
        {"path": "documents[0].paths", "reason": "必須のキーが無い"}
    ]


def test_build_settings_router_when_pending_reload(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_handlers: Callable[..., Any],
    make_terminal_config: Callable[..., TerminalConfig],
    make_status: Callable[..., SourceStatus],
) -> None:
    """読み直していない行を pending_reload で返す（正常系）。"""
    # 準備
    settings = (
        'version: "1"\n'
        "clone: /tmp/clone\n"
        "sources:\n"
        "  - id: b\n"
        "    config: /tmp/b/dev-docs.yaml\n"
        "  - id: a\n"
        "    config: /tmp/a/dev-docs.yaml\n"
        "  - id: fresh\n"
        "    config: /tmp/fresh/dev-docs.yaml\n"
    )
    write_files(tmp_path, {"settings.yaml": settings})
    statuses = [
        make_status("a", 0, config=("/tmp/a/dev-docs.yaml",)),
        make_status("b", 1, config=("/tmp/b/dev-docs.yaml",)),
    ]
    terminal = make_terminal_config(file=tmp_path / "settings.yaml")
    handlers = make_handlers(terminal=terminal, registry=FakeRegistry(statuses))
    app = FastAPI()
    app.include_router(build_settings_router(handlers))
    client = TestClient(app)
    # 実行
    response = client.get("/_api/settings/sources")
    # 検証
    rows = response.json()["sources"]
    assert response.status_code == 200
    assert [(row["id"], row["status"]) for row in rows] == [
        ("b", "serving"),
        ("a", "serving"),
        ("fresh", "pending_reload"),
    ]


def test_build_settings_router_when_put(
    make_handlers: Callable[..., Any],
    make_status: Callable[..., SourceStatus],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """保存して状態を返す（正常系）。"""
    # 準備
    saved: list[list[SourceEntry]] = []

    def fake_save_sources(sources: list[SourceEntry], **kwargs: Any) -> list[SourceStatus]:
        saved.append(list(sources))
        return [make_status("a", 0)]

    monkeypatch.setattr(route_module, "save_sources", fake_save_sources)
    handlers = make_handlers(settings_lock=threading.Lock())
    app = FastAPI()
    app.include_router(build_settings_router(handlers))
    client = TestClient(app)
    body = {"sources": [{"id": "a", "config": ["/tmp/a/dev-docs.yaml"]}]}
    # 実行
    response = client.put(
        "/_api/settings/sources", json=body, headers={"Sec-Fetch-Site": "same-origin"}
    )
    # 検証
    assert response.status_code == 200
    assert response.json()["sources"][0]["status"] == "serving"
    assert saved[0][0].id == "a"
