from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

USAGE_LINE = "範囲のファイルを作った・消した・改名したら、管理用の YAML の行を修正する"
WORKPLACE = "/_admin/session-context"


def _post(env: Any, body: dict[str, Any]) -> Any:
    """`POST /_admin/session-context` をフックと同じく Origin なしで呼ぶ。"""
    client: TestClient = env.client
    return client.post(WORKPLACE, json=body)


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_sync_file_set: Callable[..., dict[str, str]],
    add_worktree: Callable[..., Any],
) -> None:
    """ワークツリーから使える配信元と使い方・警告を返す（正常系）。"""
    # 準備
    sample = make_source("sample", sample_sync_file_set(1))
    worktree = add_worktree(sample.folder)
    notes = make_source("notes", git=False, scope_read=[sample.folder / "**"])
    env = make_server(sample, notes)
    # 実行
    response = _post(env, {"cwd": str(worktree), "reason": "startup"})
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert {item["id"]: item["access"] for item in body["sources"]} == {
        "sample": "read_write",
        "notes": "read",
    }
    assert "- sample（読み書き）" in body["context"]
    assert "- notes（読み取りだけ）" in body["context"]
    assert USAGE_LINE in body["context"]
    assert len(body["warnings"]) == 1
    assert body["warnings"][0].startswith("sample: 管理用の YAML に無いファイル")
    assert body["forgotten"] is False


def test_normal_when_cleared(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """/clear の後は、そのセッションの返し済みの記録を削除する（正常系）。"""
    # 準備
    sample = make_source("sample")
    env = make_server(sample)
    cwd = str(sample.folder)
    first = env.call("search_docs", cwd=cwd, session_id="s1", ids=["doc-1"], view="full")
    again = env.call("search_docs", cwd=cwd, session_id="s1", ids=["doc-1"], view="full")
    # 実行
    response = _post(env, {"cwd": cwd, "session_id": "s1", "reason": "clear"})
    # 検証
    after = env.call("search_docs", cwd=cwd, session_id="s1", ids=["doc-1"], view="full")
    assert response.json()["forgotten"] is True
    assert "この会話で返し済み" in again.text
    assert "この会話で返し済み" not in after.text
    assert after.text == first.text


def test_normal_when_no_source_available(
    tmp_path: Any, make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """どの scope にも当たらない作業場所では、setup の案内だけを返す（正常系）。"""
    # 準備
    env = make_server(make_source("sample"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # 実行
    response = _post(env, {"cwd": str(elsewhere)})
    # 検証
    body = response.json()
    assert body["sources"] == []
    assert "/dev-docs:setup" in body["context"]
    assert USAGE_LINE not in body["context"]


def test_error_when_input_invalid(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """reason が選択肢の外だと 422 を返し、記録を削除しない（異常系）。"""
    # 準備
    sample = make_source("sample")
    env = make_server(sample)
    cwd = str(sample.folder)
    env.call("search_docs", cwd=cwd, session_id="s1", ids=["doc-1"], view="full")
    # 実行
    response = _post(env, {"cwd": cwd, "session_id": "s1", "reason": "restart"})
    # 検証
    again = env.call("search_docs", cwd=cwd, session_id="s1", ids=["doc-1"], view="full")
    assert response.status_code == 422
    assert any("reason" in item["path"] for item in response.json()["errors"])
    assert "この会話で返し済み" in again.text
