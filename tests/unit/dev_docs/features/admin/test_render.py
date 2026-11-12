from __future__ import annotations

from dev_docs.features.admin.render import _source_row, render_status
from dev_docs.features.admin.types import (
    ProjectIndexState,
    ServerStatus,
    SourceState,
    TerminalState,
)

SETTINGS_FILE = "/home/u/.config/dev-docs/settings.yaml"
REFUSED = "接続を拒否されました（Connection refused）"


def _status(
    sources: list[SourceState],
    *,
    error: str | None = None,
    leftover_sources: list[str] | None = None,
) -> ServerStatus:
    """サーバーの状態を作る（`error` があれば project-index につながらない）。"""
    return ServerStatus(
        address="http://127.0.0.1:8781/",
        version="0.3.0",
        pid=4242,
        terminal=TerminalState(file=SETTINGS_FILE, version_state="current"),
        project_index=ProjectIndexState(
            address="http://127.0.0.1:8786", reachable=error is None, error=error
        ),
        sources=sources,
        leftover_sources=leftover_sources or [],
    )


def test_render_status() -> None:
    """配信元の表を組み立てる（正常系）。"""
    # 準備
    status = _status(
        [
            SourceState(id="sample", status="serving", errors=[]),
            SourceState(
                id="broken",
                status="not_served",
                errors=["documents[0].paths: 必須のキーが無い"],
            ),
        ]
    )
    # 実行
    result = render_status(status)
    # 検証
    assert result.splitlines() == [
        "http://127.0.0.1:8781/ dev-docs 0.3.0（pid 4242）",
        f"端末の設定: {SETTINGS_FILE}（current）",
        "project-index: http://127.0.0.1:8786（つながっている）",
        "| source | 状態 |",
        "| --- | --- |",
        "| sample | serving |",
        "| broken | not_served（documents[0].paths: 必須のキーが無い） |",
    ]


def test_render_status_when_no_sources() -> None:
    """配信元が無い（正常系）。"""
    # 準備
    status = _status([])
    # 実行
    result = render_status(status)
    # 検証
    assert result.splitlines()[3] == "配信元: なし"


def test_render_status_when_unreachable() -> None:
    """project-index につながらない（正常系）。"""
    # 準備
    status = _status([], error=REFUSED)
    # 実行
    result = render_status(status)
    # 検証
    assert result.splitlines()[2:4] == [
        f"project-index: http://127.0.0.1:8786（つながらない: {REFUSED}）",
        "配信元: project-index につながらないため取得できません",
    ]


def test_render_status_when_leftover_sources() -> None:
    """端末の設定に残った sources（正常系）。"""
    # 準備
    status = _status([], leftover_sources=["sample", "notes"])
    # 実行
    result = render_status(status)
    # 検証
    assert result.splitlines()[-1] == (
        "端末の設定に残った sources: sample・notes（project-index の端末の設定へ追加してください）"
    )


def test_source_row() -> None:
    """配信中の行（正常系）。"""
    # 実行
    result = _source_row(SourceState(id="sample", status="serving", errors=[]))
    # 検証
    assert result == "| sample | serving |"


def test_source_row_when_not_served() -> None:
    """配信していない行（正常系）。"""
    # 準備
    state = SourceState(id="broken", status="not_served", errors=["a: 誤り", "b: 誤り"])
    # 実行
    result = _source_row(state)
    # 検証
    assert result == "| broken | not_served（a: 誤り、b: 誤り） |"
