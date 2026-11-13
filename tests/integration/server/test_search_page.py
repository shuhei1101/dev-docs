from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, RealIndex, ServerEnv, doc


def _server(index: RealIndex, make_server: Callable[..., ServerEnv]) -> ServerEnv:
    """文書 2 の本文だけが語「ページング」を含む sample を配信する本物の project-index につなぐ。"""
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
    """語を含む文書だけを一致した箇所つきで返す（正常系）。"""
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
    """空の語と長すぎる語を断る（異常系）。"""
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
