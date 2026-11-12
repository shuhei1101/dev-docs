from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.migrate.service import apply_migration, plan_migration, resolve_target
from dev_docs.features.migrate.types import (
    ConfigNewerError,
    DestructiveStepBlockedError,
    MigrationConfigInvalidError,
    MigrationFailedError,
    MigrationStep,
    MigrationTarget,
    ProjectIndexUnreachableMigrationError,
)
from dev_docs.integrations.project_index.types import AddSourceResult
from dev_docs.shared.errors import ProjectIndexResponseError, ProjectIndexUnreachableError
from dev_docs.shared.yaml_io import load_roundtrip, load_yaml

SETTINGS_V1 = 'version: "1"\nclone: /x\nlog_dir: /logs\n'
SOURCES_V1 = (
    'version: "1"\nclone: /x\nsources:\n'
    "  - id: sample\n    config: /s/dev-docs.yaml\n"
    "  - id: notes\n    config: /n/dev-docs.yaml\n"
    "  - id: extra\n    config: /e/dev-docs.yaml\n"
)
NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
BACKUP_NAME = "settings.yaml.bak-20261029T120000"
PROJECT_INDEX = "http://127.0.0.1:8786"
# 配信元の行を書き出さない移し替えの引数
OPTIONS: dict[str, Any] = {"export_source": None, "project_index": PROJECT_INDEX, "now": NOW}


def _step(op: str, path: str, **overrides: Any) -> MigrationStep:
    """手順 1 つを作る。"""
    values: dict[str, Any] = {
        "version": "2",
        "op": op,
        "path": path,
        "to": None,
        "value": None,
        "description": "手順",
    }
    values.update(overrides)
    return MigrationStep(**values)


@pytest.fixture
def settings_file(tmp_path: Path) -> Path:
    """`version: "1"` の端末の設定を書いたファイルを返す。"""
    path = tmp_path / "settings.yaml"
    path.write_text(SETTINGS_V1, encoding="utf-8")
    return path


def _target(file: Path, current: str = "2") -> MigrationTarget:
    """端末の設定の移し替えの対象を作る。"""
    return MigrationTarget(kind="settings", file=file, current=current)


def test_resolve_target() -> None:
    """端末の設定を対象にする（正常系）。"""
    # 実行
    target = resolve_target(env={"DEV_DOCS_CONFIG": "/tmp/s.yaml"})
    # 検証
    assert target.kind == "settings"
    assert target.file == Path("/tmp/s.yaml")


def test_plan_migration(settings_file: Path, write_steps: Callable[..., None]) -> None:
    """当てる手順を返す（正常系）。"""
    # 準備
    write_steps(
        "settings",
        "2",
        [{"op": "rename", "path": "log_dir", "to": "state_dir", "description": "改名"}],
    )
    # 実行
    data, steps = plan_migration(_target(settings_file))
    # 検証
    assert data["version"] == "1"
    assert [step.op for step in steps] == ["rename"]


def test_plan_migration_when_current(settings_file: Path, write_steps: Callable[..., None]) -> None:
    """同じバージョンなら手順は空（正常系）。"""
    # 準備
    write_steps("settings", "2", [{"op": "delete", "path": "log_dir", "description": "削除"}])
    # 実行
    _, steps = plan_migration(_target(settings_file, current="1"))
    # 検証
    assert steps == []


def test_plan_migration_when_newer(tmp_path: Path) -> None:
    """新しすぎる設定（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text('version: "9"\nclone: /x\n', encoding="utf-8")
    # 実行・検証
    with pytest.raises(ConfigNewerError):
        plan_migration(_target(path, current="1"))


def test_plan_migration_when_no_version(tmp_path: Path) -> None:
    """version が無い（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text("clone: ~/dev-docs\n", encoding="utf-8")
    # 実行・検証
    with pytest.raises(MigrationConfigInvalidError):
        plan_migration(_target(path))


def test_apply_migration(settings_file: Path) -> None:
    """手順を当ててバックアップを取る（正常系）。"""
    # 準備
    data = load_roundtrip(settings_file.read_text(encoding="utf-8"))
    steps = [_step("rename", "log_dir", to="state_dir")]
    # 実行
    outcome = apply_migration(
        _target(settings_file), data, steps, allow_destructive=False, **OPTIONS
    )
    # 検証
    assert load_yaml(settings_file.read_text(encoding="utf-8")) == {
        "version": "2",
        "clone": "/x",
        "state_dir": "/logs",
    }
    assert outcome.backup == settings_file.parent / BACKUP_NAME
    assert outcome.backup.read_text(encoding="utf-8") == SETTINGS_V1


def test_apply_migration_when_record(settings_file: Path) -> None:
    """手順が空なら version だけを書き換える（正常系）。"""
    # 準備
    data = load_roundtrip(settings_file.read_text(encoding="utf-8"))
    # 実行
    outcome = apply_migration(_target(settings_file), data, [], allow_destructive=False, **OPTIONS)
    # 検証
    assert load_yaml(settings_file.read_text(encoding="utf-8")) == {
        "version": "2",
        "clone": "/x",
        "log_dir": "/logs",
    }
    assert outcome.backup.read_text(encoding="utf-8") == SETTINGS_V1


def test_apply_migration_when_destructive(settings_file: Path) -> None:
    """破壊的な手順で止める（異常系）。"""
    # 準備
    data = load_roundtrip(settings_file.read_text(encoding="utf-8"))
    steps = [_step("delete", "log_dir")]
    # 実行・検証
    with pytest.raises(DestructiveStepBlockedError):
        apply_migration(_target(settings_file), data, steps, allow_destructive=False, **OPTIONS)
    assert settings_file.read_text(encoding="utf-8") == SETTINGS_V1
    assert list(settings_file.parent.glob("*.bak-*")) == []


def test_apply_migration_when_invalid_result(settings_file: Path) -> None:
    """新しいスキーマに違反する（異常系）。"""
    # 準備
    data = load_roundtrip(settings_file.read_text(encoding="utf-8"))
    steps = [_step("delete", "clone")]
    # 実行・検証
    with pytest.raises(MigrationFailedError):
        apply_migration(_target(settings_file), data, steps, allow_destructive=True, **OPTIONS)
    assert settings_file.read_text(encoding="utf-8") == SETTINGS_V1


def test_apply_migration_when_changed(settings_file: Path) -> None:
    """読んだ後に変わったファイルを書かない（異常系）。"""
    # 準備
    data = load_roundtrip(settings_file.read_text(encoding="utf-8"))
    changed = 'version: "1"\nclone: /changed\nlog_dir: /logs\n'
    settings_file.write_text(changed, encoding="utf-8")
    steps = [_step("rename", "log_dir", to="state_dir")]
    # 実行・検証
    with pytest.raises(MigrationFailedError):
        apply_migration(_target(settings_file), data, steps, allow_destructive=False, **OPTIONS)
    assert settings_file.read_text(encoding="utf-8") == changed


def _export_step() -> MigrationStep:
    """`sources` を project-index へ書き出す手順を作る。"""
    return _step("export_sources", "sources")


def _exporter(
    results: dict[str, AddSourceResult | Exception], sent: list[dict[str, Any]]
) -> Callable[[Mapping[str, Any]], AddSourceResult]:
    """行の id ごとに決めた結果を返すか例外を送る、配信元の行の書き出しの偽物を作る。"""

    def _export(row: Mapping[str, Any]) -> AddSourceResult:
        sent.append(dict(row))
        result = results[str(row["id"])]
        if isinstance(result, Exception):
            raise result
        return result

    return _export


def test_apply_migration_when_export_sources(tmp_path: Path) -> None:
    """移せた行を消し、移せなかった行を残す（正常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SOURCES_V1, encoding="utf-8")
    data = load_roundtrip(SOURCES_V1)
    sent: list[dict[str, Any]] = []
    export = _exporter(
        {
            "sample": AddSourceResult(added=True),
            "notes": AddSourceResult(added=False, same=True),
            "extra": AddSourceResult(added=False, same=False),
        },
        sent,
    )
    # 実行
    outcome = apply_migration(
        _target(path),
        data,
        [_export_step()],
        allow_destructive=False,
        export_source=export,
        project_index=PROJECT_INDEX,
        now=NOW,
    )
    # 検証
    written = load_yaml(path.read_text(encoding="utf-8"))
    assert written["sources"] == [{"id": "extra", "config": "/e/dev-docs.yaml"}]
    assert (written["project_index"], written["version"]) == (PROJECT_INDEX, "2")
    assert outcome.kept == ["extra"]
    assert sent[0]["config"] == ["/s/dev-docs.yaml"]
    assert outcome.backup.read_text(encoding="utf-8") == SOURCES_V1


def test_apply_migration_when_export_unreachable(tmp_path: Path) -> None:
    """project-index につながらない（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SOURCES_V1, encoding="utf-8")
    export = _exporter(
        {
            "sample": AddSourceResult(added=True),
            "notes": ProjectIndexUnreachableError(address=PROJECT_INDEX, reason="拒否"),
        },
        [],
    )
    # 実行・検証
    with pytest.raises(ProjectIndexUnreachableMigrationError):
        apply_migration(
            _target(path),
            load_roundtrip(SOURCES_V1),
            [_export_step()],
            allow_destructive=False,
            export_source=export,
            project_index=PROJECT_INDEX,
            now=NOW,
        )
    assert path.read_text(encoding="utf-8") == SOURCES_V1
    assert list(tmp_path.glob("*.bak-*")) == []


def test_apply_migration_when_export_unexpected_status(tmp_path: Path) -> None:
    """project-index が予期しないステータスを返す（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SOURCES_V1, encoding="utf-8")
    error = ProjectIndexResponseError(
        message="project-index が 500 を返しました: boom", status_code=500, summary="boom"
    )
    export = _exporter({"sample": error}, [])
    # 実行・検証
    with pytest.raises(MigrationFailedError, match="500"):
        apply_migration(
            _target(path),
            load_roundtrip(SOURCES_V1),
            [_export_step()],
            allow_destructive=False,
            export_source=export,
            project_index=PROJECT_INDEX,
            now=NOW,
        )
    assert path.read_text(encoding="utf-8") == SOURCES_V1
