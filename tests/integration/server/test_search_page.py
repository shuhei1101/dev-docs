from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, RealIndex, ServerEnv, doc, row


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
