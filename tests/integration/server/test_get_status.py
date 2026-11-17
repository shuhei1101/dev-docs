from __future__ import annotations

import json
from collections.abc import Callable
from importlib.metadata import version

from .conftest import IndexSource, MockIndex, ServerEnv, sample_docs

BROKEN_ERRORS = [{"path": "documents[0].paths", "reason": "必須のキーが無い"}]


def test_normal(mock_index: MockIndex, make_server: Callable[..., ServerEnv]) -> None:
    """project-index の配信元の状態を返却する（正常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    mock_index.serve("broken", IndexSource(errors=BROKEN_ERRORS))
    env = make_server(mock_index)
    # 実行
    markdown = env.call_admin("status")
    result = env.call_admin("status", format="json")
    # 検証
    sources = {item["id"]: item for item in result.data["sources"]}
    assert not markdown.is_error
    assert result.data["version"] == version("dev-docs")
    assert result.data["project_index"]["reachable"] is True
    assert result.data["project_index"]["address"] == mock_index.address
    assert sources["sample"]["status"] == "serving"
    assert sources["broken"]["status"] == "not_served"
    assert sources["broken"]["errors"] == ["documents[0].paths: 必須のキーが無い"]
    assert result.structured == json.loads(result.text)
    assert "| sample | serving |" in markdown.text


def test_normal_when_project_index_unreachable(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index につながらなくても、つながらないことを返却する（正常系）。"""
    # 準備
    env = make_server(sample_index)
    sample_index.stop()
    # 実行
    result = env.call_admin("status", format="json")
    markdown = env.call_admin("status")
    # 検証
    assert not result.is_error
    assert result.data["project_index"]["reachable"] is False
    assert result.data["project_index"]["error"]
    # 空の値は MCP の結果から落ちる
    assert result.data.get("sources", []) == []
    assert "配信元: project-index につながらないため取得できません" in markdown.text


def test_normal_when_leftover_sources(
    sample_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """前のバージョンから残った sources を返却する（正常系）。"""
    # 準備
    env = make_server(
        sample_index, extra="sources:\n  - id: extra\n    config: /x/project-index.yaml\n"
    )
    # 実行
    result = env.call_admin("status", format="json")
    markdown = env.call_admin("status")
    # 検証
    assert result.data["leftover_sources"] == ["extra"]
    assert "端末の設定に残った sources: extra（project-index の端末の設定へ追加してください）" in (
        markdown.text
    )


def test_normal_when_source_loading(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """project-index が読み込みを終えていない配信元を loading で返却する（正常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource(docs={None: sample_docs()}))
    mock_index.serve("slow", IndexSource(docs={None: sample_docs()}))
    mock_index.loading = {"slow"}
    env = make_server(mock_index)
    # 実行
    result = env.call_admin("status", format="json")
    markdown = env.call_admin("status")
    # 検証
    sources = {item["id"]: item["status"] for item in result.data["sources"]}
    queries = [path for method, path, _ in mock_index.received if path.startswith("/sources?")]
    assert sources == {"sample": "serving", "slow": "loading"}
    assert queries
    assert all("include_loading=true" in path for path in queries)
    assert "| slow | loading |" in markdown.text
