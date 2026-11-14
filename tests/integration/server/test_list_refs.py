from __future__ import annotations

import subprocess
from collections.abc import Callable

from .conftest import IndexSource, RealIndex, ServerEnv, sample_docs


def test_normal(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """ブランチ・タグ・最近の commit を返却する（正常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    repo = real_index.root / "sources" / "sample"
    for args in (["branch", "feat/x"], ["tag", "v0.1.0"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/sample/refs")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["git"] is True
    assert body["defaultRef"] == "develop"
    assert {branch["name"] for branch in body["branches"]} >= {"develop", "feat/x"}
    assert [tag["name"] for tag in body["tags"]] == ["v0.1.0"]
    assert [commit["subject"] for commit in body["commits"]] == [
        "文書（2026-11-01T10:00:00+09:00）",
        "配信元の設定",
    ]


def test_normal_when_non_git_source(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """Git 管理外の配信元は git: false を返却する（正常系）。"""
    # 準備
    real_index.serve("notes", IndexSource(docs={None: sample_docs()}, git=False))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/notes/refs")
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["git"] is False
    assert (body["branches"], body["tags"], body["commits"]) == ([], [], [])


def test_error_when_source_not_found(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """無い配信元を断る（異常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/sources/unknown/refs")
    # 検証
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "unknown" in response.json()["detail"]
