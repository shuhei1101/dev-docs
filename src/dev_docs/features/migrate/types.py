"""設定の移し替えの手順・対象・例外の型と終了コード。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

from dev_docs.main import EXIT_CONFIG_INVALID

# パッケージの中の手順のフォルダ。`{MIGRATIONS_DIR}/{kind}/{バージョン}/steps.yaml` を読み込む
MIGRATIONS_DIR = "migrations"
STEPS_FILE = "steps.yaml"
# 対象と同じフォルダに配置するバックアップの名前。時刻は `%Y%m%dT%H%M%S`
BACKUP_FORMAT = "{name}.bak-{time}"
BACKUP_TIME_FORMAT = "%Y%m%dT%H%M%S"
EXIT_MIGRATION_FAILED = 4
EXIT_DESTRUCTIVE_BLOCKED = 5
EXIT_CONFIG_NEWER = 6
EXIT_PROJECT_INDEX_UNREACHABLE = 7
# sources を project-index へ移す手順を持つ端末の設定の version
SOURCES_EXPORT_VERSION = "2"


@dataclass(frozen=True)
class MigrationStep:
    """`steps.yaml` の 1 行。"""

    version: str
    op: Literal["rename", "add", "delete", "lift", "unwrap", "export_sources"]
    path: str
    description: str
    to: str | None = None
    value: Any = None
    match: dict[str, Any] | None = None
    take: str | None = None

    @property
    def destructive(self) -> bool:
        """値を捨てる手順か（値を指さない削除）。"""
        return self.op == "delete" and self.value is None


@dataclass(frozen=True)
class MigrationTarget:
    """移し替える設定のファイルと種類。"""

    kind: Literal["settings"]
    file: Path
    current: str


@dataclass(frozen=True)
class MigrationOutcome:
    """バックアップのパスと、project-index へ移さなかった行。"""

    backup: Path
    kept: list[str] = field(default_factory=list)


class MigrationError(Exception):
    """`dev-docs migrate` が終了コードに対応させる例外の基底。"""

    exit_code: ClassVar[int]


class MigrationConfigInvalidError(MigrationError):
    """対象の設定が無い・読み込めない・`version` が無い。"""

    exit_code = EXIT_CONFIG_INVALID


class MigrationFailedError(MigrationError):
    """手順を適用できない、新しいスキーマに違反する、書き込む前にファイルが変わった。"""

    exit_code = EXIT_MIGRATION_FAILED


class DestructiveStepBlockedError(MigrationError):
    """破壊的な手順があり `--allow-destructive` が無い。"""

    exit_code = EXIT_DESTRUCTIVE_BLOCKED


class ConfigNewerError(MigrationError):
    """対象の `version` が読み込めるバージョンより新しい。"""

    exit_code = EXIT_CONFIG_NEWER


class ProjectIndexUnreachableMigrationError(MigrationError):
    """`export_sources` の手順で、project-index の端末の設定の API につながらない。"""

    exit_code = EXIT_PROJECT_INDEX_UNREACHABLE

    def __init__(self, address: str, reason: str) -> None:
        super().__init__(
            f"project-index（{address}）に接続できませんでした。{reason}\n"
            "project-index を起動してから、dev-docs migrate を再実行してください。"
        )
        self.address = address
        self.reason = reason
