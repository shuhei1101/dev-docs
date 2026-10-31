from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

# 使い分けは文書の MCP の instructions にある旨の行
POINTER_LINE = (
    "探す・読む・書くときの使い分けと書き方は、文書の MCP（dev-docs）の instructions にあります。"
)
# 文脈に置かない使い方・タグの行の語
USAGE_WORDS = ("describe(source)", 'group_by="tags"', "action:")
WORKPLACE = "/_admin/session-context"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "integration-test", "version": "0"},
    },
}
CONTEXT_MAX_CHARS = 1000
TAG_HEADER = "タグ:"
# 字数の上限を超える配信元の数・ID の長さを揃える埋め草・説明
MANY_SOURCES = 40
ID_FILLER = "x" * 13
LONG_DESCRIPTION = "説明" * 50
TAG_RULES = (
    "複合語は単語まで分けてタグにする",
    "`action:`",
    "`topic:`",
    "`tool:`",
    "配信元にタグの規約があれば",
)


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
    """ワークツリーから使える配信元と警告を返す（正常系）。"""
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
    assert len(body["warnings"]) == 1
    assert body["warnings"][0].startswith("sample: 管理用の YAML に無いファイル")
    assert f"- {body['warnings'][0]}" in body["context"]
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
    assert "instructions" not in body["context"]


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


def _tag_lines(text: str) -> str:
    """`タグ:` の行から最後までを返す。"""
    return text[text.index(TAG_HEADER) :]


def _many_sources(
    workplace: Path,
    make_source: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> list[Any]:
    """作業場所に書ける、24 字の ID と 100 字の説明を持つ配信元を `MANY_SOURCES` 件作る。"""
    specs = []
    for index in range(MANY_SOURCES):
        source_id = f"source-{index:03d}-{ID_FILLER}"
        config = sample_config_text(name=source_id, description=LONG_DESCRIPTION)
        specs.append(
            make_source(
                source_id,
                sample_file_set(**{"dev-docs.yaml": config}),
                git=False,
                scope_read=[workplace],
                scope_write=[workplace],
            )
        )
    return specs


def test_normal_when_usage_pointer_included(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """文脈はタグの行を持たず、使い分けは文書の MCP の instructions にある旨を 1 行で示す（正常系）。"""
    # 準備
    sample = make_source("sample")
    env = make_server(sample)
    # 実行
    response = _post(env, {"cwd": str(sample.folder), "reason": "startup"})
    initialized = env.client.post("/mcp/", headers=MCP_HEADERS, json=INITIALIZE)
    # 検証
    context = response.json()["context"]
    instructions = initialized.json()["result"]["instructions"]
    assert response.status_code == 200
    assert context.splitlines().count(POINTER_LINE) == 1
    assert [word for word in USAGE_WORDS if word in context] == []
    assert all(rule in _tag_lines(instructions) for rule in TAG_RULES)
    assert len(context) <= CONTEXT_MAX_CHARS


def test_normal_when_context_over_limit(
    tmp_path: Path,
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """配信元が多く 1,000 字を超えるとき、説明を省き、配信元の行を減らして残りの件数を添える（正常系）。"""
    # 準備
    workplace = tmp_path / "workplace"
    workplace.mkdir()
    specs = _many_sources(workplace, make_source, sample_file_set, sample_config_text)
    env = make_server(*specs)
    # 実行
    response = _post(env, {"cwd": str(workplace), "reason": "startup"})
    # 検証
    body = response.json()
    context = body["context"]
    assert response.status_code == 200
    assert len(context) <= CONTEXT_MAX_CHARS
    assert LONG_DESCRIPTION not in context
    assert "- source-000-xxxxxxxxxxxxx（読み書き）" in context
    assert "source-039-xxxxxxxxxxxxx" not in context
    assert "- ほか " in context
    assert POINTER_LINE in context
    assert len(body["sources"]) == MANY_SOURCES
