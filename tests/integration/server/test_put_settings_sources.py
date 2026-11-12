from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .conftest import IndexSource, MockIndex, ServerEnv, sample_docs

ORIGIN = {"Origin": "http://127.0.0.1:8781"}
SAMPLE_ROW: dict[str, Any] = {
    "id": "sample",
    "config": ["/repo/sample/project-index.yaml"],
    "scope": {"read": ["/repo/**"]},
}
EXTRA_ROW: dict[str, Any] = {"id": "extra", "config": ["/repo/extra/project-index.yaml"]}


def _two_sources(mock: MockIndex) -> None:
    """sample を端末の設定の行に並べ、extra は配信元の設定だけを用意する。"""
    mock.serve("sample", IndexSource(docs={None: sample_docs()}), scope={"read": ["/repo/**"]})
    mock.sources["extra"] = IndexSource(docs={None: sample_docs()})


def _saved_rows(mock: MockIndex) -> list[list[dict[str, Any]]]:
    """モックが受けた保存の行の並び。"""
    return [body["sources"] for method, _, body in mock.received if method == "PUT"]


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """配信元を追加して保存し、再起動せずに配信する（正常系）。"""
    # 準備
    _two_sources(mock_index)
    env = make_server(mock_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [SAMPLE_ROW, {**EXTRA_ROW, "config": EXTRA_ROW["config"][0]}]},
        headers=ORIGIN,
    )
    docs = env.client.get("/_api/sources/extra/docs")
    # 検証
    [saved] = _saved_rows(mock_index)
    assert response.status_code == 200
    assert [(item["id"], item["status"]) for item in response.json()["sources"]] == [
        ("sample", "serving"),
        ("extra", "serving"),
    ]
    assert saved == [SAMPLE_ROW, EXTRA_ROW]
    assert docs.status_code == 200


def test_normal_when_source_disabled(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """enabled: false で保存し、配信を止める（正常系）。"""
    # 準備
    _two_sources(mock_index)
    mock_index.rows.append(dict(EXTRA_ROW))
    env = make_server(mock_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [SAMPLE_ROW, {**EXTRA_ROW, "enabled": False}]},
        headers=ORIGIN,
    )
    extra = env.client.get("/_api/sources/extra/docs")
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    [saved] = _saved_rows(mock_index)
    statuses = {item["id"]: item["status"] for item in response.json()["sources"]}
    assert statuses["extra"] == "disabled"
    assert saved[1]["enabled"] is False
    assert extra.status_code == 404
    assert sample.status_code == 200


def test_normal_when_source_deleted(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """行を除いて保存し、配信元のフォルダは残す（正常系）。"""
    # 準備
    _two_sources(mock_index)
    mock_index.rows.append(dict(EXTRA_ROW))
    folder = tmp_path / "extra"
    folder.mkdir()
    (folder / "project-index.yaml").write_text("name: extra\n", encoding="utf-8")
    env = make_server(mock_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources", json={"sources": [SAMPLE_ROW]}, headers=ORIGIN
    )
    extra = env.client.get("/_api/sources/extra/docs")
    # 検証
    assert response.status_code == 200
    assert _saved_rows(mock_index) == [[SAMPLE_ROW]]
    assert (folder / "project-index.yaml").read_text(encoding="utf-8") == "name: extra\n"
    assert extra.status_code == 404


def test_normal_when_added_source_invalid(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """端末の設定は保存し、読み直しの検証で外した配信元を not_served で返す（正常系）。"""
    # 準備
    _two_sources(mock_index)
    mock_index.sources["broken"] = IndexSource(
        errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}]
    )
    broken_row = {"id": "broken", "config": ["/repo/broken/project-index.yaml"]}
    env = make_server(mock_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources", json={"sources": [SAMPLE_ROW, broken_row]}, headers=ORIGIN
    )
    broken = env.client.get("/_api/sources/broken/docs")
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    statuses = {item["id"]: item for item in response.json()["sources"]}
    assert response.status_code == 200
    assert statuses["broken"]["status"] == "not_served"
    assert [error["path"] for error in statuses["broken"]["errors"]] == ["documents[0].paths"]
    assert broken_row in _saved_rows(mock_index)[0]
    assert broken.status_code == 404
    assert sample.status_code == 200


def test_error_when_cross_origin(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """画面と別のオリジンからの保存を断る（異常系）。"""
    # 準備
    _two_sources(mock_index)
    env = make_server(mock_index)
    body = {"sources": [SAMPLE_ROW]}
    # 実行
    other = env.client.put(
        "/_api/settings/sources", json=body, headers={"Origin": "http://127.0.0.1:9999"}
    )
    cross_site = env.client.put(
        "/_api/settings/sources", json=body, headers={"Sec-Fetch-Site": "cross-site"}
    )
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert other.status_code == 403
    assert cross_site.status_code == 403
    assert _saved_rows(mock_index) == []
    assert sample.status_code == 200


def test_error_when_body_invalid(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """型の合わない本文を project-index へ送らずに断り、違反を全て返す（異常系）。"""
    # 準備
    _two_sources(mock_index)
    env = make_server(mock_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [SAMPLE_ROW, {"id": "extra", "enabled": "maybe"}]},
        headers=ORIGIN,
    )
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert response.status_code == 400
    assert {error["path"] for error in response.json()["errors"]} == {
        "sources[1].config",
        "sources[1].enabled",
    }
    assert _saved_rows(mock_index) == []
    assert sample.status_code == 200


def test_error_when_project_index_rejects(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index の 422 はそのまま 422 で、それ以外の失敗は 502 で返す（異常系）。"""
    # 準備
    _two_sources(mock_index)
    errors = [{"path": "sources[1].id", "reason": "英小文字・数字・- だけ"}]
    mock_index.queued[("PUT", "/settings/sources")] = [
        (422, {"detail": "検証に失敗", "errors": errors}),
        (500, {"detail": "壊れた"}),
    ]
    env = make_server(mock_index)
    body = {"sources": [SAMPLE_ROW, EXTRA_ROW]}
    # 実行
    rejected = env.client.put("/_api/settings/sources", json=body, headers=ORIGIN)
    failed = env.client.put("/_api/settings/sources", json=body, headers=ORIGIN)
    # 検証
    assert rejected.status_code == 422
    assert rejected.json()["errors"] == errors
    assert failed.status_code == 502
    assert "500" in failed.json()["detail"]
