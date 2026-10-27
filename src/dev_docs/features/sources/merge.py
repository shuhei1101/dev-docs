"""配信元の設定の YAML のマージ。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

TABLE_KEYS = frozenset({"documents", "validators", "converters", "generators"})


def merge_configs(values: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """配信元の設定の YAML の値を上から順に重ねる。"""
    raise NotImplementedError
