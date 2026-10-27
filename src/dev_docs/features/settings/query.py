"""端末の設定の読み込み。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dev_docs.features.settings.types import TerminalConfig
from dev_docs.shared.errors import Violation

DEFAULT_CONFIG_PATH = "~/.config/dev-docs/settings.yaml"
CONFIG_ENV = "DEV_DOCS_CONFIG"
PORT_ENV = "DEV_DOCS_PORT"
SETTINGS_SCHEMA = "schemas/settings.schema.yaml"
SETTINGS_VERSION = "1"


def config_path(env: Mapping[str, str]) -> Path:
    """環境変数から端末の設定のパスを決める。"""
    raise NotImplementedError


def load_terminal_config(path: Path) -> TerminalConfig:
    """`settings.yaml` を読み、スキーマの違反を全て集めてから端末の設定にする。"""
    raise NotImplementedError


def validate_terminal_config(value: Any) -> list[Violation]:
    """端末の設定の値をスキーマと行の間の決まりで確かめ、違反を全て返す。"""
    raise NotImplementedError


def listen_port(config: TerminalConfig, env: Mapping[str, str]) -> int:
    """`DEV_DOCS_PORT` を優先して待ち受けのポートを決める。"""
    raise NotImplementedError
