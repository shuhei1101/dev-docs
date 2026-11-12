from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, MockIndex, ServerEnv, sample_docs

REFS = {
    "git": True,
    "defaultRef": "develop",
    "branches": [
        {"name": "develop", "commit": "b2"},
        {"name": "feat/x", "commit": "b2"},
    ],
    "tags": [{"name": "v0.1.0", "commit": "b2"}],
    "commits": [
        {"commit": "b2", "date": "2026-11-02T10:00:00+09:00", "subject": "docs: 改名"},
        {"commit": "a1", "date": "2026-11-01T10:00:00+09:00", "subject": "init"},
    ],
}


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """ブランチ・タグ・最近の commit を返す（正常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}, refs=REFS))
    env = make_server(mock_index)
    # 実行
    response = env.client.get("/_api/sources/sample/refs")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["git"] is True
    assert body["defaultRef"] == "develop"
    assert {branch["name"] for branch in body["branches"]} >= {"develop", "feat/x"}
    assert [tag["name"] for tag in body["tags"]] == ["v0.1.0"]
    assert [commit["subject"] for commit in body["commits"]] == ["docs: 改名", "init"]


def test_normal_when_non_git_source(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """Git 管理外の配信元は git: false を返す（正常系）。"""
    # 準備
    mock_index.serve("notes", IndexSource(docs={None: sample_docs()}, git=False))
    env = make_server(mock_index)
    # 実行
    response = env.client.get("/_api/sources/notes/refs")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["git"] is False
    assert (body["branches"], body["tags"], body["commits"]) == ([], [], [])


def test_error_when_source_not_found(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """無い配信元を断る（異常系）。"""
    # 準備
    env = make_server(sample_index)
    # 実行
    response = env.client.get("/_api/sources/unknown/refs")
    # 検証
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "unknown" in response.json()["detail"]
