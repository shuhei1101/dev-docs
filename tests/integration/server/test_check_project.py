from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def _listing(folder: Path) -> dict[str, str]:
    """フォルダの下のファイルのパスと中身を集める。"""
    return {
        str(path.relative_to(folder)): path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_sync_file_set: Callable[..., dict[str, str]],
) -> None:
    """検証に通る配信元の違反 0 件と同期の件数を返す（正常系）。"""
    # 準備
    sample = make_source("sample", sample_sync_file_set(1), git=False)
    env = make_server(sample)
    before = _listing(sample.folder)
    # 実行
    result = env.call_admin("check_project", path=str(sample.folder), format="json")
    # 検証
    assert not result.is_error
    assert "violations" not in result.data
    assert "missing_paths" not in result.data
    assert "script_errors" not in result.data
    assert result.data["version_state"] == "current"
    assert result.data["sync"]["unindexed_files"] == 1
    assert [item["path"] for item in result.data["sync"]["items"]] == ["src: src/extra0.py"]
    assert _listing(sample.folder) == before


def test_normal_when_files_excluded(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_sync_file_set: Callable[..., dict[str, str]],
) -> None:
    """除外の条件に当たるファイルを索引に無いファイルとして数えない（正常系）。"""
    # 準備
    files = sample_sync_file_set(0)
    files.update(
        {
            "src/files.yaml": "files: []\n",
            "src/a.py": "a = 1\n",
            "src/b.py": "b = 2\n",
            "src/pkg/__init__.py": "",
            "src/uv.lock": "version = 1\n",
        }
    )
    sample = make_source("sample", files, git=False)
    (sample.folder / "src" / "logo.png").write_bytes(b"\x00PNG\r\n")
    env = make_server(sample)
    # 実行
    result = env.call_admin("check_project", path=str(sample.folder), format="json")
    # 検証
    assert not result.is_error
    assert result.data["sync"]["unindexed_files"] == 2
    assert [item["path"] for item in result.data["sync"]["items"]] == [
        "src: src/a.py",
        "src: src/b.py",
    ]


def test_normal_when_records_schema_mismatch(
    tmp_path: Path,
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
) -> None:
    """records の行のスキーマが行に合わなければ、その行の schema を違反にする（正常系）。"""
    # 準備
    env = make_server(make_source("sample"))
    before = env.handlers.registry.statuses()
    folder = tmp_path / "mismatch"
    folder.mkdir()
    (folder / "dev-docs.yaml").write_text(
        "name: mismatch\n"
        "documents:\n"
        "  - id: docs\n"
        "    paths: [files.yaml]\n"
        "    schema: schemas/files.schema.yaml\n"
        "    records: files\n"
        "    body_file: path\n",
        encoding="utf-8",
    )
    (folder / "schemas").mkdir()
    (folder / "schemas" / "files.schema.yaml").write_text(
        "title: file\ntype: object\nrequired: [files]\nproperties:\n  files:\n    type: array\n",
        encoding="utf-8",
    )
    (folder / "files.yaml").write_text("files:\n  - path: a.md\n", encoding="utf-8")
    (folder / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = env.call_admin("check_project", path=str(folder), format="json")
    # 検証
    violations = result.data["violations"]
    assert [item["path"] for item in violations] == ["documents[0].schema"]
    assert "properties.files.items" in violations[0]["rule"]
    assert "sync" not in result.data
    assert env.handlers.registry.statuses() == before


def test_normal_when_config_has_violations(tmp_path: Path, make_server: Callable[..., Any]) -> None:
    """スキーマに違反する設定と、書く前の `config` の違反を返す（正常系）。"""
    # 準備
    env = make_server()
    folder = tmp_path / "draft"
    folder.mkdir()
    (folder / "dev-docs.yaml").write_text(
        "name: draft\ndocuments:\n  - id: sample\n    paths: [docs/*.yaml]\n"
        "    schema: schemas/none.schema.yaml\n",
        encoding="utf-8",
    )
    broken = "name: draft\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
    # 実行
    result = env.call_admin("check_project", path=str(folder), config=broken, format="json")
    # 検証
    assert any(item["path"] == "documents[0].paths" for item in result.data["violations"])
    assert "sync" not in result.data


def test_normal_when_config_legacy(tmp_path: Path, make_server: Callable[..., Any]) -> None:
    """前の形式のキーを持つ設定の違反と、設定のバージョンが古いことを返す（正常系）。"""
    # 準備
    env = make_server()
    legacy = (
        'version: "1"\n'
        "name: legacy\n"
        "documents:\n"
        "  - id: notes\n"
        "    paths: [docs/*.md]\n"
        "    schema: schemas/sample.schema.yaml\n"
        "    type: markdown\n"
        "    defaults:\n"
        "      - paths: [docs/**]\n"
        "        tags: [doc]\n"
        "  - id: rules\n"
        "    paths: [docs/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
        "    metadata:\n"
        "      name: {type: ref, field: title}\n"
    )
    # 実行
    result = env.call_admin("check_project", path=str(tmp_path), config=legacy, format="json")
    # 検証
    paths = {item["path"] for item in result.data["violations"]}
    assert {"documents[0].type", "documents[0].defaults", "documents[1].metadata.name"} <= paths
    assert result.data["version_state"] == "old"
    assert result.data["config_version"] == "1"


def test_error_when_config_not_found(tmp_path: Path, make_server: Callable[..., Any]) -> None:
    """dev-docs.yaml の無いフォルダを指すと断る（異常系）。"""
    # 準備
    env = make_server()
    folder = tmp_path / "empty"
    folder.mkdir()
    # 実行
    result = env.call_admin("check_project", path=str(folder))
    # 検証
    assert result.is_error
    assert result.text.startswith("ConfigNotFoundError")
    assert str(folder / "dev-docs.yaml") in result.text


def test_error_when_config_unparsable(tmp_path: Path, make_server: Callable[..., Any]) -> None:
    """読めない config を渡すと、行と理由を返して断る（異常系）。"""
    # 準備
    env = make_server()
    # 実行
    result = env.call_admin("check_project", path=str(tmp_path), config="name: [")
    # 検証
    assert result.is_error
    assert result.text.startswith("ConfigParseError")
