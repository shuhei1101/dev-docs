"""配信元の読み込みと検証。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from dev_docs.features.settings.types import SourceEntry
from dev_docs.features.sources.types import (
    SOURCE_CONFIG_VERSION,
    ServedSource,
    SourceConfig,
    SourceStatus,
)
from dev_docs.shared.errors import Violation

SOURCE_SCHEMA = "schemas/dev-docs.schema.yaml"

__all__ = [
    "SOURCE_CONFIG_VERSION",
    "SOURCE_SCHEMA",
    "check_scripts",
    "compare_config_version",
    "load_source",
    "load_source_at",
    "validate_source_config",
]


def validate_source_config(value: dict[str, Any], *, root: Path) -> list[Violation]:
    """マージした設定をスキーマ・行の参照・ファイルの有無で確かめ、違反を全て返す。"""
    raise NotImplementedError


def check_scripts(config: SourceConfig, *, root: Path) -> list[Violation]:
    """検査・変換・生成の行のコマンドを動かさずに確かめる。"""
    raise NotImplementedError


def compare_config_version(version: str) -> Literal["same", "older", "newer"]:
    """配信元の設定のバージョンをサーバーの読めるバージョンと比べる。"""
    raise NotImplementedError


def load_source(entry: SourceEntry, *, index: int) -> tuple[ServedSource | None, SourceStatus]:
    """端末の設定の 1 行から配信元の設定を読んで検証し、配信中の配信元と状態を作る。"""
    raise NotImplementedError


def load_source_at(source: ServedSource, root: Path) -> ServedSource:
    """配信中の配信元の設定を、作業ツリーかワークツリーの同じ場所から読み直す。"""
    raise NotImplementedError
