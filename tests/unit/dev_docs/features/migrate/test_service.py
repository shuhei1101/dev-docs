from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.migrate.service import (
    _export_sources,
    apply_migration,
    plan_migration,
    resolve_target,
)
from dev_docs.features.migrate.types import (
    ConfigNewerError,
    DestructiveStepBlockedError,
    MigrationConfigInvalidError,
    MigrationFailedError,
    MigrationStep,
    MigrationTarget,
    ProjectIndexUnreachableMigrationError,
    SourcesPort,
)
from dev_docs.integrations.project_index.types import SettingsSourcesView, SourceState
from dev_docs.shared.errors import (
    InvalidArgumentError,
    ProjectIndexResponseError,
    ProjectIndexUnreachableError,
    Violation,
)
from dev_docs.shared.yaml_io import load_roundtrip, load_yaml

SETTINGS_V1 = 'version: "1"\nclone: /x\nlog_dir: /logs\n'
SOURCES_V1 = (
    'version: "1"\nclone: /x\nsources:\n'
    "  - id: sample\n    config: /s/dev-docs.yaml\n"
    "  - id: notes\n    config: /n/dev-docs.yaml\n"
    "  - id: extra\n    config: /e/dev-docs.yaml\n"
)
SAMPLE_V1 = 'version: "1"\nclone: /x\nsources:\n  - id: sample\n    config: /s/dev-docs.yaml\n'
NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
BACKUP_NAME = "settings.yaml.bak-20261029T120000"
PROJECT_INDEX = "http://127.0.0.1:8786"
# 配信元の行を書き出さない移し替えの引数
OPTIONS: dict[str, Any] = {"sources_port": None, "project_index": PROJECT_INDEX, "now": NOW}


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
    """`version: "1"` の端末の設定を書き込んだファイルを返却する。"""
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
    """適用する手順を返却する（正常系）。"""
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
    """手順を適用してバックアップを取る（正常系）。"""
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
    """読み込んだ後に変わったファイルに書き込まない（異常系）。"""
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


def _pi_row(row_id: str | None, config: str, **extra: Any) -> dict[str, Any]:
    """project-index の端末の設定の取得の行（`SettingsSourcesView.rows` の 1 件）を作る。"""
    return {
        "id": row_id,
        "config": [config],
        "enabled": True,
        "scope": {"read": [], "write": None},
        "outside_read": True,
        **extra,
    }


def _view(
    rows: list[dict[str, Any]], *, version: str = "v1", status: str = "serving"
) -> SettingsSourcesView:
    """取得の応答を作る。状態の `id` は行の `id` と同じにする。"""
    return SettingsSourcesView(
        settings_path="/pi/settings.yaml",
        rows=rows,
        states=[SourceState(id=row["id"], status=status, config=row["config"]) for row in rows],  # type: ignore[arg-type]
        version=version,
    )


class FakePort:
    """取得の応答を順に返却し、保存を記録するか例外を送出する、移す先の端末の設定の API の偽物。"""

    def __init__(
        self,
        views: list[SettingsSourcesView | Exception],
        *,
        save_error: Exception | None = None,
    ) -> None:
        self._views: Iterator[SettingsSourcesView | Exception] = iter(views)
        self._save_error = save_error
        self.fetched = 0
        self.saved: list[tuple[list[dict[str, Any]], str | None]] = []

    def fetch(self) -> SettingsSourcesView:
        self.fetched += 1
        view = next(self._views)
        if isinstance(view, Exception):
            raise view
        return view

    def save(self, rows: list[dict[str, Any]], expected_version: str | None) -> None:
        self.saved.append((rows, expected_version))
        if self._save_error is not None:
            raise self._save_error

    def port(self) -> SourcesPort:
        return SourcesPort(fetch=self.fetch, save=self.save)


UNREACHABLE = ProjectIndexUnreachableError(
    address=PROJECT_INDEX, reason="45 秒以内に応答がありませんでした"
)
SEND_KEYS = {"id", "config", "enabled", "scope", "outside_read"}


def _data(text: str) -> Any:
    """往復編集で読み込んだ端末の設定を返却する。"""
    return load_roundtrip(text)


def test_apply_migration_when_export_sources(tmp_path: Path) -> None:
    """sources を project-index へ移す（正常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SAMPLE_V1, encoding="utf-8")
    fake = FakePort([_view([])])
    # 実行
    outcome = apply_migration(
        _target(path),
        load_roundtrip(SAMPLE_V1),
        [_export_step()],
        allow_destructive=False,
        sources_port=fake.port(),
        project_index=PROJECT_INDEX,
        now=NOW,
    )
    # 検証
    written = load_yaml(path.read_text(encoding="utf-8"))
    assert len(fake.saved) == 1
    assert "sources" not in written
    assert (written["project_index"], written["version"]) == (PROJECT_INDEX, "2")
    assert outcome.backup.read_text(encoding="utf-8") == SAMPLE_V1


def test_apply_migration_when_export_unreachable(tmp_path: Path) -> None:
    """移す先につながらない（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SOURCES_V1, encoding="utf-8")
    fake = FakePort([UNREACHABLE])
    # 実行
    with pytest.raises(ProjectIndexUnreachableMigrationError):
        apply_migration(
            _target(path),
            load_roundtrip(SOURCES_V1),
            [_export_step()],
            allow_destructive=False,
            sources_port=fake.port(),
            project_index=PROJECT_INDEX,
            now=NOW,
        )
    # 検証
    assert path.read_text(encoding="utf-8") == SOURCES_V1
    assert list(tmp_path.glob("*.bak-*")) == []


def test_apply_migration_when_export_unexpected_status(tmp_path: Path) -> None:
    """project-index の想定しない応答（異常系）。"""
    # 準備
    path = tmp_path / "settings.yaml"
    path.write_text(SOURCES_V1, encoding="utf-8")
    error = ProjectIndexResponseError(
        message="project-index が 500 を返しました: boom", status_code=500, summary="boom"
    )
    fake = FakePort([_view([])], save_error=error)
    # 実行
    with pytest.raises(MigrationFailedError, match="500"):
        apply_migration(
            _target(path),
            load_roundtrip(SOURCES_V1),
            [_export_step()],
            allow_destructive=False,
            sources_port=fake.port(),
            project_index=PROJECT_INDEX,
            now=NOW,
        )
    # 検証
    assert path.read_text(encoding="utf-8") == SOURCES_V1


def test_export_sources() -> None:
    """今の行に加えて 1 回で保存する（正常系）。"""
    # 準備
    data = _data(SOURCES_V1)
    fake = FakePort(
        [
            _view(
                [
                    _pi_row("notes", "/n/dev-docs.yaml"),
                    _pi_row("extra", "/e/dev-docs.yaml", enabled=False),
                ]
            )
        ]
    )
    # 実行
    kept, unresolved = _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert len(fake.saved) == 1
    rows, version = fake.saved[0]
    assert [row["id"] for row in rows] == ["notes", "extra", "sample"]
    assert all(set(row) <= SEND_KEYS for row in rows)
    assert version == "v1"
    assert [row["id"] for row in data["sources"]] == ["extra"]
    assert data["project_index"] == PROJECT_INDEX
    assert (kept, unresolved) == (["extra"], [])


def test_export_sources_when_id_omitted(tmp_path: Path) -> None:
    """`id` を省いた行を `name` で照らす（正常系）。"""
    # 準備
    config = tmp_path / "dev-docs.yaml"
    config.write_text("name: notes\n", encoding="utf-8")
    data = _data(f'version: "1"\nclone: /x\nsources:\n  - config: {config}\n')
    fake = FakePort([_view([_pi_row("notes", str(config))])])
    # 実行
    _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert fake.saved == []
    assert "sources" not in data


def test_export_sources_when_name_unresolved(tmp_path: Path) -> None:
    """ID を求められない行を残す（正常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    data = _data(f'version: "1"\nclone: /x\nsources:\n  - config: {missing}\n')
    fake = FakePort([_view([])])
    # 実行
    kept, unresolved = _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert fake.saved == []
    assert [str(row["config"]) for row in data["sources"]] == [str(missing)]
    assert (kept, unresolved) == ([], [str(missing)])


def test_export_sources_when_save_timeout() -> None:
    """保存を打ち切っても再取得で確認する（正常系）。"""
    # 準備
    data = _data(SAMPLE_V1)
    fake = FakePort(
        [_view([]), _view([_pi_row("sample", "/s/dev-docs.yaml")], status="pending_reload")],
        save_error=UNREACHABLE,
    )
    # 実行
    _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert fake.fetched == 2
    assert "sources" not in data


def test_export_sources_when_save_timeout_with_id_omitted(tmp_path: Path) -> None:
    """再読み込みの途中でも `id` を省いた行の保存を確認する（正常系）。"""
    # 準備
    config = tmp_path / "dev-docs.yaml"
    config.write_text("name: notes\n", encoding="utf-8")
    data = _data(f'version: "1"\nclone: /x\nsources:\n  - config: {config}\n')
    fake = FakePort(
        [_view([]), _view([_pi_row(None, str(config))], status="pending_reload")],
        save_error=UNREACHABLE,
    )
    # 実行
    _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert "sources" not in data


def test_export_sources_when_save_unconfirmed() -> None:
    """再取得しても保存を確認できない（異常系）。"""
    # 準備
    data = _data(SAMPLE_V1)
    fake = FakePort([_view([]), _view([])], save_error=UNREACHABLE)
    # 実行
    with pytest.raises(ProjectIndexUnreachableMigrationError) as caught:
        _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert caught.value.unconfirmed is True


def test_export_sources_when_fetch_unreachable() -> None:
    """最初の取得がつながらない（異常系）。"""
    # 準備
    data = _data(SAMPLE_V1)
    fake = FakePort([UNREACHABLE])
    # 実行
    with pytest.raises(ProjectIndexUnreachableMigrationError) as caught:
        _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert caught.value.unconfirmed is False
    assert fake.saved == []


def test_export_sources_when_rejected() -> None:
    """受け付けなかった行を ID で出す（異常系）。"""
    # 準備
    text = (
        'version: "1"\nclone: /x\nsources:\n'
        "  - id: sample\n    config: /s/dev-docs.yaml\n"
        "  - id: broken\n    config: /b/dev-docs.yaml\n    enabled: maybe\n"
    )
    data = _data(text)
    error = InvalidArgumentError(
        message="引数が正しくありません: 1 件",
        violations=[Violation(path="sources[2].enabled", rule="bool ではない")],
    )
    fake = FakePort([_view([_pi_row("extra", "/e/dev-docs.yaml")])], save_error=error)
    # 実行
    with pytest.raises(MigrationFailedError, match=r"(?m)^broken: "):
        _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert [row["id"] for row in data["sources"]] == ["sample", "broken"]


def test_export_sources_when_conflict() -> None:
    """取得した後に project-index の端末の設定が変わった（異常系）。"""
    # 準備
    data = _data(SAMPLE_V1)
    error = ProjectIndexResponseError(
        message="project-index が 409 を返しました: conflict", status_code=409, summary="conflict"
    )
    fake = FakePort([_view([])], save_error=error)
    # 実行
    with pytest.raises(MigrationFailedError, match="409") as caught:
        _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert "やり直" in str(caught.value)


def test_export_sources_when_disabled_id_omitted(tmp_path: Path) -> None:
    """配信していない `id` 省略の行を `name` で照らす（正常系）。"""
    # 準備
    config = tmp_path / "dev-docs.yaml"
    config.write_text("name: notes\n", encoding="utf-8")
    data = _data(
        f'version: "1"\nclone: /x\nsources:\n  - config: {config}\n'
        "  - id: sample\n    config: /s/dev-docs.yaml\n"
    )
    fake = FakePort([_view([_pi_row("sources[0]", str(config), enabled=False)], status="disabled")])
    # 実行
    kept, _ = _export_sources(data, fake.port(), PROJECT_INDEX)
    # 検証
    assert len(fake.saved) == 1
    rows, _ = fake.saved[0]
    assert "id" not in rows[0]
    assert rows[1]["id"] == "sample"
    assert kept == ["notes"]
    assert [str(row["config"]) for row in data["sources"]] == [str(config)]
