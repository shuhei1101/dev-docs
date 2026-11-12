from __future__ import annotations

from collections.abc import Callable

from .conftest import SETTINGS_PATH, IndexSource, MockIndex, ServerEnv, sample_docs


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """配信元の一覧を配信中で返す（正常系）。"""
    # 準備
    mock_index.serve(
        "sample", IndexSource(docs={None: sample_docs()}), scope={"read": ["/repo/**"]}
    )
    env = make_server(mock_index)
    # 実行
    response = env.client.get("/_api/settings/sources")
    mock_index.rows = []
    empty = env.client.get("/_api/settings/sources")
    # 検証
    body = response.json()
    [sample] = body["sources"]
    assert response.status_code == 200
    assert body["settingsPath"] == SETTINGS_PATH
    assert (sample["id"], sample["status"]) == ("sample", "serving")
    assert sample["config"] == ["/repo/sample/project-index.yaml"]
    assert sample["scope"] == {"read": ["/repo/**"], "write": None}
    assert empty.status_code == 200
    assert empty.json()["sources"] == []


def test_normal_when_source_not_served(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """配信していない・無効・設定が古い配信元を状態と理由つきで返す（正常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    mock_index.serve(
        "broken",
        IndexSource(errors=[{"path": "documents[0].paths", "reason": "必須のキーが無い"}]),
    )
    mock_index.serve(
        "legacy",
        IndexSource(docs={None: sample_docs()}, config_version={"config": "1", "server": "2"}),
    )
    mock_index.serve("archive", IndexSource(docs={None: sample_docs()}), enabled=False)
    env = make_server(mock_index)
    # 実行
    response = env.client.get("/_api/settings/sources")
    # 検証
    sources = {item["id"]: item for item in response.json()["sources"]}
    assert response.status_code == 200
    assert (sources["sample"]["status"], sources["legacy"]["status"]) == ("serving", "serving")
    assert sources["broken"]["status"] == "not_served"
    assert sources["broken"]["errors"] == [
        {"path": "documents[0].paths", "reason": "必須のキーが無い"}
    ]
    assert sources["legacy"]["configVersion"] == {"config": "1", "server": "2"}
    assert (sources["archive"]["status"], sources["archive"]["enabled"]) == ("disabled", False)


def test_normal_when_pending_reload(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """読み直していない行を pending_reload で返し、他の行は自分の状態で返す（正常系）。"""
    # 準備
    mock_index.rows.append({"config": ["/repo/fresh/project-index.yaml"]})
    mock_index.serve("notes", IndexSource(docs={None: sample_docs()}))
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    mock_index.pending = {0}
    env = make_server(mock_index)
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
    assert sources[0]["config"] == ["/repo/fresh/project-index.yaml"]
