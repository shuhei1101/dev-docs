from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .conftest import IndexSource, MockIndex, RealIndex, ServerEnv, doc, row

# 本物の project-index が返却した画面の検索の応答。検索のダイアログの結合テストが API の応答に使用する
MATCH_COUNT_RESPONSE = (
    Path(__file__).parents[1] / "frontend" / "support" / "search-match-count.json"
)


def _server(index: RealIndex, make_server: Callable[..., ServerEnv]) -> ServerEnv:
    """文書 2 の本文だけが単語「ページング」を含む sample を配信する本物の project-index につなぐ。"""
    documents = [
        doc("doc-1", "docs/doc-1.yaml", data={"id": "doc-1", "name": "文書 1"}),
        doc(
            "doc-2",
            "docs/doc-2.yaml",
            data={"id": "doc-2", "name": "文書 2", "description": "一覧のページングは先頭から"},
        ),
    ]
    index.serve("sample", IndexSource(docs={None: documents}))
    return make_server(index)


def test_normal(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """単語を含む文書だけを一致した箇所つきで返却する（正常系）。"""
    # 準備
    env = _server(real_index, make_server)
    # 実行
    found = env.client.get("/_api/sources/sample/search", params={"q": "ページング"})
    body = found.json()
    opened = env.client.get(f"/_api/sources/sample/docs/{body['items'][0]['path']}")
    # 検証
    assert found.status_code == 200
    assert body["totalCount"] == 1
    assert [item["path"] for item in body["items"]] == ["docs/doc-2"]
    assert any("ページング" in snippet for snippet in body["items"][0]["snippets"])
    assert opened.status_code == 200
    assert opened.json()["path"] == "docs/doc-2"


def test_error_when_query_invalid(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """空の単語と長すぎる単語を断る（異常系）。"""
    # 準備
    env = _server(real_index, make_server)
    # 実行
    empty = env.client.get("/_api/sources/sample/search", params={"q": ""})
    long = env.client.get("/_api/sources/sample/search", params={"q": "x" * 201})
    # 検証
    assert empty.status_code == 400
    assert empty.json()["errors"][0]["path"] == "q"
    assert "at least 1 character" in empty.json()["errors"][0]["reason"]
    assert long.status_code == 400
    assert long.json()["errors"][0]["path"] == "q"
    assert "at most 200 characters" in long.json()["errors"][0]["reason"]


def test_error_when_not_found(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """無い配信元・解決できないリビジョンを断る（異常系）。"""
    # 準備
    env = _server(real_index, make_server)
    # 実行
    unknown = env.client.get("/_api/sources/unknown/search", params={"q": "a"})
    no_ref = env.client.get(
        "/_api/sources/sample/search", params={"q": "a", "ref": "no-such-branch"}
    )
    # 検証
    assert unknown.status_code == 404
    assert "配信元" in unknown.json()["detail"]
    assert "unknown" in unknown.json()["detail"]
    assert no_ref.status_code == 404
    assert "no-such-branch" in no_ref.json()["detail"]


def test_normal_when_search_excluded(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """検索から除外される文書を既定の結果から除いて件数を返却し、`include_excluded` で含める（正常系）。"""
    # 準備
    documents = [
        doc(
            "doc-1",
            "docs/doc-1.yaml",
            data={"id": "doc-1", "name": "文書 1", "description": "ページングの説明"},
        ),
        doc(
            "doc-2",
            "docs/doc-2.yaml",
            data={"id": "doc-2", "name": "文書 2", "description": "ページングの例"},
        ),
    ]
    excluded = {"field": "id", "op": "eq", "values": ["doc-2"]}
    rows = [row("sample", ["docs/*.yaml"], search_exclude=excluded)]
    real_index.serve("sample", IndexSource(documents=rows, docs={None: documents}))
    env = make_server(real_index)
    # 実行
    default = env.client.get("/_api/sources/sample/search", params={"q": "ページング"})
    included = env.client.get(
        "/_api/sources/sample/search", params={"q": "ページング", "include_excluded": "true"}
    )
    # 検証
    first = default.json()
    second = included.json()
    assert default.status_code == 200
    assert first["totalCount"] == 1
    assert [(item["path"], item["excluded"]) for item in first["items"]] == [("docs/doc-1", False)]
    assert first["excludedCount"] == 1
    assert included.status_code == 200
    assert second["totalCount"] == 2
    assert sorted((item["path"], item["excluded"]) for item in second["items"]) == [
        ("docs/doc-1", False),
        ("docs/doc-2", True),
    ]
    assert second["excludedCount"] == 0


def test_normal_when_match_count(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index が返却した一致した行の数を文書ごとに返却し、返却しないときは null にする（正常系）。"""
    # 準備
    documents = [
        doc("doc-1", "docs/doc-1.yaml", data={"id": "doc-1", "name": "文書 1"}),
        doc("doc-2", "docs/doc-2.yaml", data={"id": "doc-2", "name": "文書 2"}),
    ]

    def hit(doc_id: str, name: str, extra: dict[str, int] | None = None) -> dict[str, object]:
        return {
            "path": f"docs/{doc_id}",
            "id": doc_id,
            "filePath": f"docs/{doc_id}.yaml",
            "name": name,
            "snippets": ["…ページング…"],
            **(extra or {}),
        }

    counted = IndexSource(
        docs={None: documents},
        search={
            "totalCount": 2,
            "items": [
                hit("doc-1", "文書 1", {"matchCount": 4}),
                hit("doc-2", "文書 2", {"matchCount": 1}),
            ],
        },
    )
    uncounted = IndexSource(
        docs={None: documents},
        search={"totalCount": 2, "items": [hit("doc-1", "文書 1"), hit("doc-2", "文書 2")]},
    )
    mock_index.serve("sample", counted)
    mock_index.serve("notes", uncounted)
    env = make_server(mock_index)
    # 実行
    with_count = env.client.get("/_api/sources/sample/search", params={"q": "ページング"})
    without_count = env.client.get("/_api/sources/notes/search", params={"q": "ページング"})
    # 検証
    assert with_count.status_code == 200
    assert [item["matchCount"] for item in with_count.json()["items"]] == [4, 1]
    assert without_count.status_code == 200
    assert [item["matchCount"] for item in without_count.json()["items"]] == [None, None]


def test_normal_when_match_count_from_real_index(
    match_count_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """本物の project-index が数えた本文の一致した行の数を、文書ごとに返却する（正常系）。"""
    # 準備
    rows = [row("sample", ["docs/*.yaml"]), row("notes", ["notes/files.yaml"], records="files")]
    # パスの順・名前の順（a-one・z-many・ページングの案内）と、一致した行の数の多い順
    # （z-many・a-one・ページングの案内）が違う並びになる名前にする
    bodies = {
        # 単語を含む行が 4 行（`snippets` の上限の 3 件より多い）。1 行に 2 回含む行も 1 行と数える
        "z-many": "# 概要\n\nページングの説明\n他の行\nページングの例とページングの注意\n他の行\nページング\n末尾のページング\n",
        # 単語を含む行が 1 行
        "a-one": "# 概要\n\n一覧のページング\n他の行\n",
    }
    notes = [
        doc(
            f"notes/{name}.md",
            "notes/files.yaml",
            kind="notes",
            record_index=index,
            body_path=f"notes/{name}.md",
            body=body,
            data={"path": f"{name}.md"},
        )
        for index, (name, body) in enumerate(bodies.items())
    ]
    # 本文は単語を含まず、文書の ID（パス）だけが単語を含む
    named = doc(
        "notes/ページングの案内.md",
        "notes/files.yaml",
        kind="notes",
        record_index=len(notes),
        body_path="notes/ページングの案内.md",
        body="# 概要\n\n他の行\n",
        data={"path": "ページングの案内.md"},
    )
    match_count_index.serve("sample", IndexSource(documents=rows, docs={None: [*notes, named]}))
    env = make_server(match_count_index)
    # 実行
    found = env.client.get("/_api/sources/sample/search", params={"q": "ページング"})
    # 検証
    assert found.status_code == 200
    counts = {item["path"]: item["matchCount"] for item in found.json()["items"]}
    assert counts == {
        "notes/files/notes/z-many.md": 4,
        "notes/files/notes/a-one.md": 1,
        "notes/files/notes/ページングの案内.md": 0,
    }
    assert found.json() == json.loads(MATCH_COUNT_RESPONSE.read_text(encoding="utf-8"))
