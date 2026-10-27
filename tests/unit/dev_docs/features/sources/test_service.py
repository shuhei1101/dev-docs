from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.settings.types import SourceEntry
from dev_docs.features.sources import service as service_module
from dev_docs.features.sources.service import (
    check_scripts,
    compare_config_version,
    load_source,
    load_source_at,
    validate_source_config,
)
from dev_docs.features.sources.types import ScriptEntry, ServedSource, SourceConfig
from dev_docs.shared.errors import ValidationFailedError, Violation

RULE_SCHEMA = "title: rule\ntype: object\n"


def _config_value(**overrides: Any) -> dict[str, Any]:
    """検証を通る最小の配信元の設定の値を返す。"""
    value: dict[str, Any] = {
        "name": "sample",
        "documents": [
            {
                "id": "rules",
                "type": "yaml",
                "paths": ["docs/rule/*.yaml"],
                "schema": "schemas/rule.schema.yaml",
            }
        ],
    }
    value.update(overrides)
    return value


@pytest.fixture
def source_root(tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]) -> Path:
    """スキーマのファイルを持つ配信元のフォルダを返す。"""
    root = tmp_path / "root"
    write_files(root, {"schemas/rule.schema.yaml": RULE_SCHEMA})
    return root


def test_validate_source_config(source_root: Path) -> None:
    """違反が無い（正常系）。"""
    # 準備
    value = _config_value()
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert result == []


def test_validate_source_config_when_required_missing(source_root: Path) -> None:
    """必須のキーが無い（正常系）。"""
    # 準備
    value = _config_value(
        documents=[{"id": "rules", "type": "yaml", "schema": "schemas/rule.schema.yaml"}]
    )
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert result == [Violation(path="documents[0].paths", rule="必須のキーが無い")]


def test_validate_source_config_when_unknown_key(source_root: Path) -> None:
    """表に無いキー（正常系）。"""
    # 準備
    value = _config_value(mcp={})
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert [(v.path, v.rule) for v in result] == [("mcp", "知らないキー")]


def test_validate_source_config_when_duplicate_id(source_root: Path) -> None:
    """行の ID が重なる（正常系）。"""
    # 準備
    row = {
        "id": "a",
        "type": "yaml",
        "paths": ["docs/*.yaml"],
        "schema": "schemas/rule.schema.yaml",
    }
    value = _config_value(documents=[row, dict(row)])
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert [v.path for v in result] == ["documents[1].id"]


def test_validate_source_config_when_dangling_reference(source_root: Path) -> None:
    """無い ID を指す（正常系）。"""
    # 準備
    row = {
        "id": "rules",
        "type": "yaml",
        "paths": ["docs/*.yaml"],
        "schema": "schemas/rule.schema.yaml",
        "validators": ["nope"],
    }
    value = _config_value(documents=[row], validators=[])
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert [(v.path, v.rule) for v in result] == [("documents[0].validators[0]", "存在しない ID")]


def test_validate_source_config_when_schema_missing(source_root: Path) -> None:
    """スキーマのファイルが無い（正常系）。"""
    # 準備
    row = {"id": "rules", "type": "yaml", "paths": ["docs/*.yaml"], "schema": "schemas/none.yaml"}
    value = _config_value(documents=[row])
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert [v.path for v in result] == ["documents[0].schema"]


def test_validate_source_config_when_outside_root(source_root: Path) -> None:
    """配信元の外を指す（正常系）。"""
    # 準備
    row = {
        "id": "rules",
        "type": "yaml",
        "paths": ["../x/*.md"],
        "schema": "schemas/rule.schema.yaml",
    }
    value = _config_value(documents=[row])
    # 実行
    result = validate_source_config(value, root=source_root)
    # 検証
    assert [v.path for v in result] == ["documents[0].paths[0]"]


def test_check_scripts(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
) -> None:
    """全て実行できる（正常系）。"""
    # 準備
    write_files(tmp_path, {"scripts/c.py": "print('x')\n"})
    config = make_source_config(converters=[ScriptEntry(id="c", run=["python3", "scripts/c.py"])])
    # 実行
    result = check_scripts(config, root=tmp_path)
    # 検証
    assert result == []


def test_check_scripts_when_missing(
    tmp_path: Path, make_source_config: Callable[..., SourceConfig]
) -> None:
    """スクリプトが無い（正常系）。"""
    # 準備
    config = make_source_config(
        converters=[ScriptEntry(id="c", run=["python3", "scripts/none.py"])]
    )
    # 実行
    result = check_scripts(config, root=tmp_path)
    # 検証
    assert [v.path for v in result] == ["converters[0]"]
    assert "scripts/none.py" in result[0].rule


def test_compare_config_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """同じ・古い・新しい（正常系）。"""
    # 準備
    monkeypatch.setattr(service_module, "SOURCE_CONFIG_VERSION", "2")
    # 実行
    same = compare_config_version("2")
    older = compare_config_version("1")
    newer = compare_config_version("3")
    # 検証
    assert (same, older, newer) == ("same", "older", "newer")


def test_load_source(
    git_repo: Callable[..., Path],
    sample_files: dict[str, str],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """配信する（正常系）。"""
    # 準備
    root = git_repo(sample_files)
    entry = make_entry(str(root / "dev-docs.yaml"))
    # 実行
    served, status = load_source(entry, index=0)
    # 検証
    assert served is not None
    assert served.id == "sample"
    assert served.is_git is True
    assert "rules" in served.schemas
    assert status.status == "serving"


def test_load_source_when_merged(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """複数の YAML を重ねる（正常系）。"""
    # 準備
    root = tmp_path / "ws"
    write_files(root, sample_files)
    write_files(tmp_path / "local", {"local.yaml": "description: 後の値\n"})
    entry = make_entry([str(root / "dev-docs.yaml"), str(tmp_path / "local" / "local.yaml")])
    # 実行
    served, _ = load_source(entry, index=0)
    # 検証
    assert served is not None
    assert served.config.description == "後の値"
    assert served.root == root


def test_load_source_when_disabled(make_entry: Callable[..., SourceEntry]) -> None:
    """端末の設定で無効（正常系）。"""
    # 準備
    entry = make_entry("/tmp/none/dev-docs.yaml", source_id="a", enabled=False)
    # 実行
    served, status = load_source(entry, index=0)
    # 検証
    assert served is None
    assert status.status == "disabled"


def test_load_source_when_config_missing(make_entry: Callable[..., SourceEntry]) -> None:
    """設定のファイルが無い（正常系）。"""
    # 準備
    entry = make_entry("/tmp/none.yaml", source_id="a")
    # 実行
    served, status = load_source(entry, index=0)
    # 検証
    assert served is None
    assert status.status == "not_served"
    assert [error.path for error in status.errors] == ["config[0]"]


def test_load_source_when_invalid(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_entry: Callable[..., SourceEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """検証に失敗する（正常系）。"""
    # 準備
    write_files(
        tmp_path, {"dev-docs.yaml": "name: sample\ndocuments:\n  - id: rules\n    type: yaml\n"}
    )
    entry = make_entry(str(tmp_path / "dev-docs.yaml"), source_id="sample")
    # 実行
    with caplog.at_level(logging.ERROR):
        served, status = load_source(entry, index=0)
    # 検証
    assert served is None
    assert status.status == "not_served"
    assert [error.path for error in status.errors] == ["documents[0].paths"]
    assert "sample: documents[0].paths: 必須のキーが無い" in caplog.text


def test_load_source_when_script_missing(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """スクリプトが無い（正常系）。"""
    # 準備
    config = (
        sample_files["dev-docs.yaml"]
        + "converters:\n  - id: c\n    run: [python3, scripts/none.py]\n"
    )
    write_files(tmp_path, {**sample_files, "dev-docs.yaml": config})
    entry = make_entry(str(tmp_path / "dev-docs.yaml"), source_id="sample")
    # 実行
    served, status = load_source(entry, index=0)
    # 検証
    assert served is None
    assert status.status == "not_served"
    assert [error.path for error in status.errors] == ["converters[0]"]


def test_load_source_when_version_old(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    make_entry: Callable[..., SourceEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """設定のバージョンが古い（正常系）。"""
    # 準備
    monkeypatch.setattr(service_module, "SOURCE_CONFIG_VERSION", "2")
    write_files(
        tmp_path,
        {**sample_files, "dev-docs.yaml": 'version: "1"\n' + sample_files["dev-docs.yaml"]},
    )
    entry = make_entry(str(tmp_path / "dev-docs.yaml"), source_id="sample")
    # 実行
    with caplog.at_level(logging.WARNING):
        served, status = load_source(entry, index=0)
    # 検証
    assert served is not None
    assert status.status == "serving"
    assert status.config_version == ("1", "2")
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_load_source_when_not_git(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """Git の管理外のフォルダ（正常系）。"""
    # 準備
    write_files(tmp_path / "plain", sample_files)
    entry = make_entry(str(tmp_path / "plain" / "dev-docs.yaml"))
    # 実行
    served, _ = load_source(entry, index=0)
    # 検証
    assert served is not None
    assert served.is_git is False
    assert served.repo_root is None


@pytest.fixture
def cloned_source(
    git_repo: Callable[..., Path],
    sample_files: dict[str, str],
    make_served_source: Callable[..., ServedSource],
) -> ServedSource:
    """git リポジトリのクローン本体の配信元を返す。"""
    root = git_repo(sample_files)
    return make_served_source(
        id="sample",
        root=root,
        config_files=[root / "dev-docs.yaml"],
        is_git=True,
        repo_root=root,
    )


@pytest.fixture
def worktree(cloned_source: ServedSource, run_git: Callable[..., str], tmp_path: Path) -> Path:
    """クローン本体のワークツリーを作って返す。"""
    path = tmp_path / "wt"
    run_git(cloned_source.root, "worktree", "add", "-b", "feat/x", str(path))
    return path


def test_load_source_at(
    cloned_source: ServedSource,
    worktree: Path,
    sample_files: dict[str, str],
) -> None:
    """ワークツリーの設定（正常系）。"""
    # 準備
    extra = "  - id: notes\n    type: markdown\n    paths: [docs/note/*.md]\n"
    (worktree / "dev-docs.yaml").write_text(sample_files["dev-docs.yaml"] + extra, encoding="utf-8")
    # 実行
    result = load_source_at(cloned_source, worktree)
    # 検証
    assert [row.id for row in result.config.documents] == ["rules", "notes"]
    assert result.root == worktree
    assert result.id == "sample"


def test_load_source_at_when_config_missing(cloned_source: ServedSource, worktree: Path) -> None:
    """設定のファイルが無い（異常系）。"""
    # 準備
    (worktree / "dev-docs.yaml").unlink()
    # 実行・検証
    with pytest.raises(ValidationFailedError) as exc_info:
        load_source_at(cloned_source, worktree)
    assert [v.path for v in exc_info.value.violations] == ["config[0]"]


def test_load_source_at_when_invalid(cloned_source: ServedSource, worktree: Path) -> None:
    """検証に通らない（異常系）。"""
    # 準備
    (worktree / "dev-docs.yaml").write_text(
        "name: sample\ndocuments:\n  - id: rules\n    type: yaml\n", encoding="utf-8"
    )
    # 実行・検証
    with pytest.raises(ValidationFailedError) as exc_info:
        load_source_at(cloned_source, worktree)
    assert [v.path for v in exc_info.value.violations] == ["documents[0].paths"]
