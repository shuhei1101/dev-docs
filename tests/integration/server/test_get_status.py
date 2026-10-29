from __future__ import annotations

import json
from collections.abc import Callable
from importlib.metadata import version
from typing import Any

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_sync_file_set: Callable[..., dict[str, str]],
) -> None:
    """配信中・配信していない配信元の状態を返す（正常系）。"""
    # 準備
    sample = make_source("sample", sample_sync_file_set(1))
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG})
    env = make_server(sample, broken)
    # 実行
    markdown = env.call_admin("status")
    result = env.call_admin("status", format="json")
    # 検証
    sources = {item["id"]: item for item in result.data["sources"]}
    assert not markdown.is_error
    assert result.data["version"] == version("dev-docs")
    assert sources["sample"]["status"] == "serving"
    assert sources["sample"]["sync"]["unindexed_files"] == 1
    assert sources["broken"]["status"] == "not_served"
    assert any("documents[0].paths" in error for error in sources["broken"]["errors"])
    assert result.structured == json.loads(result.text)
    assert "| sample | serving |" in markdown.text
