from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, MockIndex, ServerEnv, sample_docs

SEARCH_RESULT = {
    "totalCount": 1,
    "items": [
        {
            "id": "doc-2",
            "path": "docs/doc-2.yaml",
            "name": "文書 2",
            "snippets": ["一覧のページングは先頭から"],
        }
    ],
}


def _server(mock: MockIndex, make_server: Callable[..., ServerEnv]) -> ServerEnv:
    """文書 2 だけが語「ページング」に当たる検索の結果を返す sample につなぐ。"""
    mock.serve("sample", IndexSource(docs={None: sample_docs()}, search=SEARCH_RESULT))
    return make_server(mock)


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """語を含む文書だけを一致した箇所つきで返す（正常系）。"""
    # 準備
    env = _server(mock_index, make_server)
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
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """空の語と長すぎる語を断る（異常系）。"""
    # 準備
    env = _server(mock_index, make_server)
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


def test_error_when_not_found(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """無い配信元・解決できないリビジョンを断る（異常系）。"""
    # 準備
    env = _server(mock_index, make_server)
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
