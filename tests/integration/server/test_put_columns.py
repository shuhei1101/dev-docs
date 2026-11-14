from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, MockIndex, ServerEnv, doc, sample_docs

TABLE_DATA = {
    "id": "doc-1",
    "name": "文書 1",
    "items": [
        {"key": "k1", "label": "名称 1", "notes": "備考 1"},
        {"key": "k2", "label": "名称 2", "notes": "備考 2"},
    ],
}
ORIGIN = {"Origin": "http://127.0.0.1:8781"}


def _setup(mock: MockIndex, make_server: Callable[..., ServerEnv]) -> ServerEnv:
    """文書 1 の本文に 3 列の表がある sample につなぐ。"""
    documents = [doc("doc-1", "docs/doc-1.yaml", data=TABLE_DATA), *sample_docs()[1:]]
    mock.serve("sample", IndexSource(docs={None: documents}))
    return make_server(mock)


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """隠す列を書き込み、次の文書の取得でその列を返却する（正常系）。"""
    # 準備
    env = _setup(mock_index, make_server)
    table = env.client.get("/_api/sources/sample/docs/docs/doc-1").json()["tableKeys"][0]
    # 実行
    saved = env.client.put(
        "/_api/sources/sample/columns",
        json={"table": table, "hidden": ["label"]},
        headers=ORIGIN,
    )
    hidden = env.client.get("/_api/sources/sample/docs/docs/doc-1").json()["columns"]
    cleared = env.client.put(
        "/_api/sources/sample/columns", json={"table": table, "hidden": []}, headers=ORIGIN
    )
    after_clear = env.client.get("/_api/sources/sample/docs/docs/doc-1").json()["columns"]
    # 検証
    assert saved.status_code == 200
    assert saved.json() == {"table": table, "hidden": ["label"]}
    assert (env.state_dir / "columns" / "sample.json").is_file()
    assert {method for method, _, _ in mock_index.received} == {"GET"}
    assert hidden == {table: ["label"]}
    assert cleared.status_code == 200
    assert after_clear == {}


def test_error_when_body_invalid(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """スキーマの合わない本文を断る（異常系）。"""
    # 準備
    env = _setup(mock_index, make_server)
    # 実行
    response = env.client.put(
        "/_api/sources/sample/columns",
        json={"table": "sample:items", "hidden": "notes"},
        headers=ORIGIN,
    )
    # 検証
    assert response.status_code == 400
    assert response.json()["errors"][0]["path"] == "hidden"
    assert not (env.state_dir / "columns" / "sample.json").exists()


def test_error_when_cross_origin(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """画面と別のオリジンからの書き込みを断る（異常系）。"""
    # 準備
    env = _setup(mock_index, make_server)
    # 実行
    response = env.client.put(
        "/_api/sources/sample/columns",
        json={"table": "sample:items", "hidden": ["notes"]},
        headers={"Origin": "http://127.0.0.1:9999"},
    )
    # 検証
    assert response.status_code == 403
    assert not (env.state_dir / "columns" / "sample.json").exists()


def test_error_when_source_not_found(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """無い配信元の列の設定を書き込まない（異常系）。"""
    # 準備
    env = _setup(mock_index, make_server)
    # 実行
    response = env.client.put(
        "/_api/sources/unknown/columns",
        json={"table": "sample:items", "hidden": ["notes"]},
        headers=ORIGIN,
    )
    # 検証
    assert response.status_code == 404
    assert "unknown" in response.json()["detail"]
    assert not (env.state_dir / "columns" / "unknown.json").exists()
