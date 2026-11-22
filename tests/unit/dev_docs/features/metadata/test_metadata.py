from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from dev_docs.features.metadata.metadata import KeyMapping, build_metadata, key_mapping
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexUnreachableError

from ...conftest import FakeIndex, config_json, doc_json

TERMS_ROW = {"id": "terms", "paths": ["glossary.yaml"], "records": "terms", "alias_type": "term"}
NOTE_ROW = {"id": "note", "paths": ["notes/*.yaml"], "alias_type": "doc"}
RULE_ROW = {"id": "rule_index", "paths": ["rules.yaml"], "records": "rules"}
FILES_ROW = {"id": "files", "paths": ["files.yaml"], "records": "files", "body_file": "path"}


def _settings(kinds: list[str]) -> dict[str, Any]:
    """sample の行の `directCommit.writeApiKinds` を持つ端末の設定の取得の応答を作る。"""
    return {
        "settingsPath": "/pi/settings.yaml",
        "sources": [
            {
                "id": "sample",
                "config": ["/repo/sample/project-index.yaml"],
                "enabled": True,
                "scope": {"read": [], "write": None},
                "outsideRead": True,
                "directCommit": {"writeApiKinds": kinds},
                "status": "serving",
                "errors": [],
                "configVersion": None,
            }
        ],
        "version": "v1",
    }


def _sample_docs() -> list[dict[str, Any]]:
    """用語 2 件・`note` の文書 1 件・索引 2 件・管理用の YAML 1 件。"""
    return [
        doc_json(
            "source",
            "glossary.yaml",
            kind="terms",
            metadata={
                "id": "source",
                "name": "配信元",
                "aliases": ["source"],
                "description": "project-index.yaml を持つフォルダ",
                "alias_type": "term",
            },
            version="t1",
        ),
        doc_json(
            "kind",
            "glossary.yaml",
            kind="terms",
            metadata={"id": "kind", "name": "種類", "alias_type": "term"},
            version="t2",
        ),
        doc_json(
            "n1",
            "notes/n1.yaml",
            kind="note",
            metadata={"id": "n1", "name": "メモ", "tags": ["topic:a"], "alias_type": "doc"},
            version="n1v",
        ),
        doc_json(
            "r1",
            "rules.yaml",
            kind="rule_index",
            data={"id": "r1", "rule": "docs/rule/a.yaml", "paths": ["src/**/*.py"], "tools": []},
            version="r1v",
        ),
        doc_json(
            "r2",
            "rules.yaml",
            kind="rule_index",
            data={
                "id": "r2",
                "rule": "docs/rule/b.yaml",
                "paths": ["docs/**"],
                "tools": ["Edit"],
                "args": {"file_path": "*.md"},
            },
            version="r2v",
        ),
        doc_json(
            "f1",
            "files.yaml",
            kind="files",
            metadata={"id": "f1", "name": "a.py", "description": "エントリーポイント"},
            body_path="src/a.py",
            version="f1v",
        ),
    ]


def _kind(response: Any, kind_id: str) -> Any:
    """応答から種類 1 つを取り出す。"""
    return next(kind for kind in response.kinds if kind.id == kind_id)


def test_key_mapping() -> None:
    """対応の形ごとに解決する（正常系）。"""
    # 準備
    mappings = {
        "tags": "tags[].name",
        "name": "title",
        "skill": "skill.path",
        "main_tags": "tags[main].name",
    }
    # 実行
    results = [
        key_mapping({}, "name"),
        key_mapping(mappings, "name"),
        key_mapping(mappings, "tags"),
        key_mapping(mappings, "skill"),
        key_mapping(mappings, "main_tags"),
    ]
    # 検証
    assert results == [
        KeyMapping("name", None),
        KeyMapping("title", None),
        KeyMapping("tags", "name"),
        None,
        None,
    ]


def test_build_metadata(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """種類ごとの行と列（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(
        documents=[TERMS_ROW, NOTE_ROW, RULE_ROW, FILES_ROW]
    )
    fake_index.docs["sample"] = {None: _sample_docs()}
    fake_index.settings = _settings(["note", "terms"])
    # 実行
    response = asyncio.run(build_metadata(make_client(), "sample"))
    # 検証
    assert [kind.id for kind in response.kinds] == [
        "terms",
        "aliases",
        "tags",
        "rules",
        "config",
        "files",
    ]
    assert response.branch == "develop"
    terms = _kind(response, "terms")
    assert [row.id for row in terms.rows] == ["source", "kind"]
    assert [row.editable for row in terms.rows] == [True, True]
    assert (terms.can_add, terms.can_delete, terms.create_kind) == (True, True, "terms")
    assert terms.rows[0].values == {
        "name": "配信元",
        "aliases": ["source"],
        "description": "project-index.yaml を持つフォルダ",
    }
    assert terms.rows[0].version == "t1"
    tags = _kind(response, "tags")
    assert next(row for row in tags.rows if row.id == "n1").values["tags"] == ["topic:a"]
    rules = _kind(response, "rules")
    assert [row.editable for row in rules.rows] == [False, False]
    assert rules.rows[0].values["rule"] == "docs/rule/a.yaml"
    assert rules.rows[0].values["paths"] == ["src/**/*.py"]
    config = _kind(response, "config")
    assert {row.id: row.values["direct_commit"] for row in config.rows} == {
        "terms": "✓",
        "note": "✓",
        "rule_index": "",
        "files": "",
    }
    assert all(not row.editable for row in config.rows)
    files = _kind(response, "files")
    assert [row.values["path"] for row in files.rows] == ["src/a.py"]


def test_build_metadata_when_mapped(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """対応づけたキーの列（正常系）。"""
    # 準備
    skill_row = {
        "id": "skill",
        "paths": ["skills/*.yaml"],
        "alias_type": "skill",
        "metadata": {"tags": "tags[].name", "skill": "skill.path"},
    }
    fake_index.configs["sample"] = config_json(documents=[skill_row, RULE_ROW])
    fake_index.docs["sample"] = {
        None: [
            doc_json(
                "s1",
                "skills/s1.yaml",
                kind="skill",
                data={"id": "s1", "tags": [{"name": "topic:x", "main": True}]},
                metadata={"id": "s1", "name": "スキル", "tags": ["topic:x"]},
            )
        ]
    }
    fake_index.settings = _settings(["skill"])
    # 実行
    response = asyncio.run(build_metadata(make_client(), "sample"))
    # 検証
    tags = _kind(response, "tags")
    column = next(column for column in tags.columns if column.key == "tags")
    assert column.editable is True
    assert tags.rows[0].values["tags"] == ["topic:x"]


def test_build_metadata_when_rule_index_missing(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """索引を配信していない（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=[TERMS_ROW, NOTE_ROW])
    fake_index.docs["sample"] = {None: []}
    fake_index.settings = _settings([])
    # 実行
    response = asyncio.run(build_metadata(make_client(), "sample"))
    # 検証
    rules = _kind(response, "rules")
    assert rules.served is False
    assert rules.rows == []
    assert rules.hint is not None
    assert "id: rule_index" in rules.hint
    assert all(kind.served for kind in response.kinds if kind.id != "rules")


def test_build_metadata_when_unreachable(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    fake_index.refused = True
    # 実行・検証
    with pytest.raises(ProjectIndexUnreachableError, match="接続できませんでした"):
        asyncio.run(build_metadata(make_client(), "sample"))
