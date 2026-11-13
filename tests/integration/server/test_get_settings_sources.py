from __future__ import annotations

from collections.abc import Callable

from .conftest import IndexSource, RealIndex, ServerEnv, materialize, sample_docs


def test_normal(real_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """配信元の一覧を配信中で返す（正常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    env = make_server(real_index)
    config = str(real_index.root / "sources" / "sample" / "project-index.yaml")
    # 実行
    response = env.client.get("/_api/settings/sources")
    real_index.put_rows([])
    empty = env.client.get("/_api/settings/sources")
    # 検証
    body = response.json()
    [sample] = body["sources"]
    assert response.status_code == 200
    assert body["settingsPath"] == str(real_index.settings_path)
    assert (sample["id"], sample["status"]) == ("sample", "serving")
    assert sample["config"] == [config]
    assert sample["scope"] == {"read": [f"{real_index.root}/**"], "write": None}
    assert empty.status_code == 200
    assert empty.json()["sources"] == []


def test_normal_when_source_not_served(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """配信していない・無効・設定が古い配信元を状態と理由つきで返す（正常系）。"""
    # 準備
    real_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    real_index.serve(
        "broken",
        IndexSource(errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}]),
    )
    real_index.serve(
        "legacy",
        IndexSource(docs={None: sample_docs()}, config_version={"config": "1", "server": "3"}),
    )
    real_index.serve("archive", IndexSource(docs={None: sample_docs()}), enabled=False)
    env = make_server(real_index)
    # 実行
    response = env.client.get("/_api/settings/sources")
    # 検証
    sources = {item["id"]: item for item in response.json()["sources"]}
    assert response.status_code == 200
    assert sources["sample"]["status"] == "serving"
    assert sources["broken"]["status"] == "not_served"
    assert [error["path"] for error in sources["broken"]["errors"]] == ["documents[0].paths"]
    assert sources["legacy"]["configVersion"] == {"config": "1", "server": "3"}
    assert (sources["archive"]["status"], sources["archive"]["enabled"]) == ("disabled", False)


def test_normal_when_pending_reload(
    real_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """読み直していない行を pending_reload で返し、他の行は自分の状態で返す（正常系）。"""
    # 準備
    real_index.serve("notes", IndexSource(docs={None: sample_docs()}))
    real_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    env = make_server(real_index)
    fresh = materialize(real_index.root / "fresh", "fresh", IndexSource(docs={None: sample_docs()}))
    # project-index の起動の後に、端末の設定のファイルへ行を直接書き足す（読み直さない）
    real_index.write_rows([{"config": [str(fresh)]}, *real_index.rows])
    # 実行
    response = env.client.get("/_api/settings/sources")
    # 検証
    sources = response.json()["sources"]
    assert response.status_code == 200
    assert [(item["id"], item["status"]) for item in sources] == [
        (None, "pending_reload"),
        ("notes", "serving"),
        ("sample", "serving"),
    ]
    assert sources[0]["config"] == [str(fresh)]
