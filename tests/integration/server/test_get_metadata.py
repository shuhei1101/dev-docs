from __future__ import annotations

import subprocess
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from .conftest import RealIndex, ServerEnv, metadata_source

URL = "/_api/sources/sample/metadata"


def _kind(body: dict[str, Any], kind_id: str) -> dict[str, Any]:
    """応答から種類 1 つを取り出す。"""
    return next(kind for kind in body["kinds"] if kind["id"] == kind_id)


def _status(repo: Any) -> str:
    """配信元のクローン本体の `git status --porcelain`。"""
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def test_normal(write_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """種類ごとの行と、行ごとに直コミットできるかを返却する（正常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    before = _status(source.repo)
    # 実行
    response = env.client.get(URL)
    # 検証
    body = response.json()
    assert response.status_code == 200, body
    assert [kind["id"] for kind in body["kinds"]] == [
        "terms",
        "aliases",
        "tags",
        "rules",
        "config",
        "files",
    ]
    terms = _kind(body, "terms")
    assert sorted(row["id"] for row in terms["rows"]) == ["old-name", "source"]
    assert all(row["editable"] for row in terms["rows"])
    assert (terms["canAdd"], terms["canDelete"], terms["createKind"]) == (True, True, "terms")
    tags = _kind(body, "tags")
    assert next(row for row in tags["rows"] if row["id"] == "n1")["values"]["tags"] == ["topic:a"]
    rules = _kind(body, "rules")
    assert len(rules["rows"]) == 2
    assert not any(row["editable"] for row in rules["rows"])
    r1 = next(row for row in rules["rows"] if row["id"] == "r1")
    assert (r1["values"]["rule"], r1["values"]["paths"]) == ("docs/rule/a.yaml", ["src/**/*.py"])
    config = {row["id"]: row["values"]["direct_commit"] for row in _kind(body, "config")["rows"]}
    assert (config["note"], config["terms"], config["rule_index"]) == ("✓", "✓", "")
    files = _kind(body, "files")
    assert [row["values"]["path"] for row in files["rows"]] == ["src/a.py"]
    assert body["branch"] == "develop"
    assert _status(source.repo) == before


def test_normal_when_rule_index_not_served(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """種類 rule_index が無い配信元は、rules を配信していないことと加える行を返却する（正常系）。"""
    # 準備
    metadata_source(write_index, rule_index=False)
    env = make_server(write_index)
    # 実行
    response = env.client.get(URL)
    # 検証
    body = response.json()
    rules = _kind(body, "rules")
    assert response.status_code == 200, body
    assert (rules["served"], rules["rows"]) == (False, [])
    assert "id: rule_index" in rules["hint"]
    assert all(kind["served"] for kind in body["kinds"] if kind["id"] != "rules")


def test_error_when_source_missing(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """無い配信元は project-index の 404 を返却する（異常系）。"""
    # 準備
    metadata_source(write_index)
    env = make_server(write_index)
    # 実行
    response = env.client.get("/_api/sources/missing/metadata")
    # 検証
    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_error_when_project_index_unreachable(
    make_server: Callable[..., ServerEnv], free_port: Callable[[], int]
) -> None:
    """project-index につながらないときは、アドレスと理由を返却する（異常系）。"""
    # 準備
    address = f"http://127.0.0.1:{free_port()}"
    env = make_server(SimpleNamespace(address=address))
    # 実行
    response = env.client.get(URL)
    # 検証
    body = response.json()
    assert response.status_code == 503, body
    assert body["projectIndex"]["address"] == address
    assert body["projectIndex"]["reason"]
