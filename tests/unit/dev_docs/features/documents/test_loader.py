from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from dev_docs.features.documents.loader import (
    collect_files,
    load_file,
    split_front_matter,
)
from dev_docs.features.history.types import FileDates
from dev_docs.features.sources.types import DocumentTable, MetadataMapping
from dev_docs.shared.hashing import content_hash, value_hash
from dev_docs.shared.yaml_io import YamlLoadError


def test_collect_files(tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]) -> None:
    """glob で集める（正常系）。"""
    # 準備
    write_files(
        tmp_path,
        {
            "a/x.yaml": "x: 1\n",
            "a/b/y.yaml": "y: 1\n",
            "a/z.md": "# z\n",
            ".git/c.yaml": "c: 1\n",
        },
    )
    # 実行
    result = collect_files(tmp_path, ["a/**/*.yaml"])
    # 検証
    assert result == ["a/b/y.yaml", "a/x.yaml"]


def test_collect_files_when_overlapping_patterns(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """重なる glob（正常系）。"""
    # 準備
    write_files(tmp_path, {"a/x.yaml": "x: 1\n"})
    # 実行
    result = collect_files(tmp_path, ["a/*.yaml", "**/x.yaml"])
    # 検証
    assert result == ["a/x.yaml"]


def test_split_front_matter() -> None:
    """front matter と本文（正常系）。"""
    # 実行
    result = split_front_matter("---\nid: a\n---\n# T\n")
    # 検証
    assert result == ({"id": "a"}, "# T\n")


@pytest.mark.parametrize("text", ["# T\n", "---\nid: a\n"])
def test_split_front_matter_when_absent(text: str) -> None:
    """front matter が無い（正常系）。"""
    # 実行
    result = split_front_matter(text)
    # 検証
    assert result == ({}, text)


def test_split_front_matter_when_not_mapping() -> None:
    """front matter が配列（異常系）。"""
    # 実行・検証
    with pytest.raises(YamlLoadError):
        split_front_matter("---\n- a\n---\n")


def test_load_file_when_yaml(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """YAML の 1 ファイル 1 文書（正常系）。"""
    # 準備
    text = "id: rule-a\ntitle: A\n"
    write_files(tmp_path, {"rules/a.yaml": text})
    table = DocumentTable(
        id="rules",
        type="yaml",
        paths=["rules/*.yaml"],
        metadata={"name": MetadataMapping(type="ref", field="title")},
    )
    # 実行
    documents, problems = load_file(tmp_path, "rules/a.yaml", table, source_id="sample")
    # 検証
    assert problems == []
    assert len(documents) == 1
    assert documents[0].id == "rule-a"
    assert documents[0].metadata["name"] == "A"
    assert documents[0].version == content_hash(text)
    assert documents[0].record_index is None


def test_load_file_when_markdown(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """front matter の無い Markdown（正常系）。"""
    # 準備
    write_files(tmp_path, {"notes/x.md": "# X\n"})
    table = DocumentTable(id="notes", type="markdown", paths=["notes/*.md"])
    # 実行
    documents, _ = load_file(tmp_path, "notes/x.md", table, source_id="sample")
    # 検証
    assert documents[0].id == "notes/x"
    assert documents[0].body == "# X\n"
    assert documents[0].data == {}


def test_load_file_when_records(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """records と body_file（正常系）。"""
    # 準備
    write_files(
        tmp_path,
        {
            "src/files.yaml": "files:\n  - path: a.py\n    tags: [x]\n  - path: b.py\n",
            "src/a.py": "a = 1\n",
            "src/b.py": "b = 2\n",
        },
    )
    table = DocumentTable(
        id="src", type="yaml", paths=["src/files.yaml"], records="files", body_file="path"
    )
    # 実行
    documents, problems = load_file(tmp_path, "src/files.yaml", table, source_id="sample")
    # 検証
    assert problems == []
    assert [doc.id for doc in documents] == ["src/a", "src/b"]
    assert [doc.body for doc in documents] == ["a = 1\n", "b = 2\n"]
    assert [doc.body_path for doc in documents] == ["src/a.py", "src/b.py"]
    assert [doc.record_index for doc in documents] == [0, 1]
    assert documents[0].version == value_hash({"path": "a.py", "tags": ["x"]})


def test_load_file_when_dates(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """日時の優先順位（正常系）。"""
    # 準備
    stamped = "id: {id}\nupdated: 2026-01-02T00:00:00+09:00\n"
    write_files(
        tmp_path,
        {
            "a.yaml": stamped.format(id="a"),
            "b.yaml": stamped.format(id="b"),
            "c.yaml": "id: c\n",
        },
    )
    table = DocumentTable(id="rules", type="yaml", paths=["*.yaml"])
    dates = {
        "a.yaml": FileDates(
            created=datetime.fromisoformat("2025-12-01T00:00:00+09:00"),
            updated=datetime.fromisoformat("2025-12-05T00:00:00+09:00"),
        )
    }
    # 実行
    doc_a = load_file(tmp_path, "a.yaml", table, source_id="s", dates=dates)[0][0]
    doc_b = load_file(tmp_path, "b.yaml", table, source_id="s", dates=dates)[0][0]
    doc_c = load_file(tmp_path, "c.yaml", table, source_id="s", dates=dates)[0][0]
    # 検証
    assert doc_a.created == datetime.fromisoformat("2025-12-01T00:00:00+09:00")
    assert doc_a.updated == datetime.fromisoformat("2025-12-05T00:00:00+09:00")
    assert doc_b.created is None
    assert doc_b.updated == datetime.fromisoformat("2026-01-02T00:00:00+09:00")
    assert doc_c.created is None
    assert doc_c.updated is None


def test_load_file_when_unreadable(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """読めない YAML（異常系）。"""
    # 準備
    write_files(tmp_path, {"a.yaml": "a: [1\n"})
    table = DocumentTable(id="rules", type="yaml", paths=["*.yaml"])
    # 実行
    documents, problems = load_file(tmp_path, "a.yaml", table, source_id="sample")
    # 検証
    assert documents == []
    assert problems[0].reason == "unreadable"
    assert problems[0].detail != ""
    assert problems[0].line is not None
    assert problems[0].line >= 1
    assert problems[0].column is not None
    assert problems[0].column >= 1


def test_load_file_when_missing_body_file(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> None:
    """無い本文のファイル（異常系）。"""
    # 準備
    write_files(
        tmp_path,
        {"src/files.yaml": "files:\n  - path: none.py\n  - path: ../../x.py\n"},
    )
    table = DocumentTable(
        id="src", type="yaml", paths=["src/files.yaml"], records="files", body_file="path"
    )
    # 実行
    documents, problems = load_file(tmp_path, "src/files.yaml", table, source_id="sample")
    # 検証
    assert documents == []
    assert [problem.reason for problem in problems] == ["missing_body_file"] * 2
