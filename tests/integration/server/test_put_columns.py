from __future__ import annotations

from collections.abc import Callable
from typing import Any

TABLE_DOC = (
    "id: doc-1\n"
    "name: 文書 1\n"
    "items:\n"
    "  - {key: k1, label: 名称 1, notes: 備考 1}\n"
    "  - {key: k2, label: 名称 2, notes: 備考 2}\n"
)
ORIGIN = {"Origin": "http://127.0.0.1:8781"}


def _setup(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> Any:
    """文書 1 の本文に 3 列の表がある sample を起動する。"""
    return make_server(make_source("sample", sample_file_set(**{"docs/doc-1.yaml": TABLE_DOC})))


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """隠す列を書き、次の文書の取得でその列を返す（正常系）。"""
    # 準備
    env = _setup(make_source, make_server, sample_file_set)
    source_files = sorted(path.name for path in env.folders["sample"].rglob("*.yaml"))
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
    assert sorted(path.name for path in env.folders["sample"].rglob("*.yaml")) == source_files
    assert hidden == {table: ["label"]}
    assert cleared.status_code == 200
    assert after_clear == {}


def test_error_when_body_invalid(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """形の合わない本文を断る（異常系）。"""
    # 準備
    env = _setup(make_source, make_server, sample_file_set)
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
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """画面と別のオリジンからの書き込みを断る（異常系）。"""
    # 準備
    env = _setup(make_source, make_server, sample_file_set)
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
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """無い配信元の列の設定を書かない（異常系）。"""
    # 準備
    env = _setup(make_source, make_server, sample_file_set)
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
