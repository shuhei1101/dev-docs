from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .conftest import IndexSource, MockIndex, RealIndex, ServerEnv, materialize, sample_docs

ORIGIN = {"Origin": "http://127.0.0.1:8781"}
SAMPLE_ROW: dict[str, Any] = {
    "id": "sample",
    "config": ["/repo/sample/project-index.yaml"],
    "scope": {"read": ["/repo/**"]},
}
EXTRA_ROW: dict[str, Any] = {"id": "extra", "config": ["/repo/extra/project-index.yaml"]}


def _two_sources(index: RealIndex) -> tuple[dict[str, Any], dict[str, Any]]:
    """sample を端末の設定の行に並べ、extra は配信元の設定だけを用意して、2 つの行を返す。"""
    index.serve("sample", IndexSource(docs={None: sample_docs()}))
    extra = materialize(index.root / "sources", "extra", IndexSource(docs={None: sample_docs()}))
    sample_row = dict(index.rows[0])
    return sample_row, {"id": "extra", "config": [str(extra)], "scope": sample_row["scope"]}


def _ids(index: RealIndex) -> list[Any]:
    """project-index の端末の設定のファイルの行の ID の並び。"""
    return [item.get("id") for item in index.file_rows()]


def test_normal(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """配信元を追加して保存し、再起動せずに配信する（正常系）。"""
    # 準備
    sample_row, extra_row = _two_sources(real_index)
    env = make_server(real_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [sample_row, {**extra_row, "config": extra_row["config"][0]}]},
        headers=ORIGIN,
    )
    docs = env.client.get("/_api/sources/extra/docs")
    # 検証
    saved = real_index.file_rows()
    assert response.status_code == 200
    assert [(item["id"], item["status"]) for item in response.json()["sources"]] == [
        ("sample", "serving"),
        ("extra", "serving"),
    ]
    assert [item["id"] for item in saved] == ["sample", "extra"]
    assert saved[0]["config"] == sample_row["config"]
    assert saved[1]["config"] == extra_row["config"]
    assert docs.status_code == 200


def test_normal_when_source_disabled(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """enabled: false で保存し、配信を止める（正常系）。"""
    # 準備
    sample_row, extra_row = _two_sources(real_index)
    real_index.rows.append(dict(extra_row))
    env = make_server(real_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [sample_row, {**extra_row, "enabled": False}]},
        headers=ORIGIN,
    )
    extra = env.client.get("/_api/sources/extra/docs")
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    saved = real_index.file_rows()
    statuses = {item["id"]: item["status"] for item in response.json()["sources"]}
    assert statuses["extra"] == "disabled"
    assert saved[1]["enabled"] is False
    assert extra.status_code == 404
    assert sample.status_code == 200


def test_normal_when_source_deleted(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """行を除いて保存し、配信元のフォルダは残す（正常系）。"""
    # 準備
    sample_row, extra_row = _two_sources(real_index)
    real_index.rows.append(dict(extra_row))
    folder = real_index.root / "sources" / "extra"
    before = (folder / "project-index.yaml").read_text(encoding="utf-8")
    env = make_server(real_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources", json={"sources": [sample_row]}, headers=ORIGIN
    )
    extra = env.client.get("/_api/sources/extra/docs")
    # 検証
    assert response.status_code == 200
    assert _ids(real_index) == ["sample"]
    assert (folder / "project-index.yaml").read_text(encoding="utf-8") == before
    assert extra.status_code == 404


def test_normal_when_added_source_invalid(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """端末の設定は保存し、読み直しの検証で外した配信元を not_served で返す（正常系）。"""
    # 準備
    sample_row, _ = _two_sources(real_index)
    broken = materialize(
        real_index.root / "sources",
        "broken",
        IndexSource(errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}]),
    )
    broken_row = {"id": "broken", "config": [str(broken)], "scope": sample_row["scope"]}
    env = make_server(real_index)
    # 実行
    response = env.client.put(
        "/_api/settings/sources", json={"sources": [sample_row, broken_row]}, headers=ORIGIN
    )
    broken_docs = env.client.get("/_api/sources/broken/docs")
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    statuses = {item["id"]: item for item in response.json()["sources"]}
    assert response.status_code == 200
    assert statuses["broken"]["status"] == "not_served"
    assert [error["path"] for error in statuses["broken"]["errors"]] == ["documents[0].paths"]
    assert _ids(real_index) == ["sample", "broken"]
    assert broken_docs.status_code == 404
    assert sample.status_code == 200


def test_error_when_cross_origin(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """画面と別のオリジンからの保存を断る（異常系）。"""
    # 準備
    sample_row, _ = _two_sources(real_index)
    env = make_server(real_index)
    before = real_index.file_rows()
    body = {"sources": [sample_row]}
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
    assert real_index.file_rows() == before
    assert sample.status_code == 200


def test_error_when_body_invalid(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """型の合わない本文を project-index へ送らずに断り、違反を全て返す（異常系）。"""
    # 準備
    sample_row, _ = _two_sources(real_index)
    env = make_server(real_index)
    before = real_index.file_rows()
    # 実行
    response = env.client.put(
        "/_api/settings/sources",
        json={"sources": [sample_row, {"id": "extra", "enabled": "maybe"}]},
        headers=ORIGIN,
    )
    sample = env.client.get("/_api/sources/sample/docs")
    # 検証
    assert response.status_code == 400
    assert {error["path"] for error in response.json()["errors"]} == {
        "sources[1].config",
        "sources[1].enabled",
    }
    assert real_index.file_rows() == before
    assert sample.status_code == 200


def test_error_when_project_index_rejects(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index の 422 はそのまま 422 で、それ以外の失敗は 502 で返す（異常系）。"""
    # 準備
    mock_index.serve(
        "sample", IndexSource(docs={None: sample_docs()}), scope={"read": ["/repo/**"]}
    )
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
