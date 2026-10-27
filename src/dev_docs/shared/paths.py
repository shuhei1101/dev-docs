"""作業場所の glob の照合とパスの正規化。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def match_glob(path: Path, patterns: Sequence[str], *, base: Path | None = None) -> bool:
    """作業場所のパスが glob の 1 つに当たるかを返す。"""
    raise NotImplementedError


def normalize_path(path: str | Path) -> Path:
    """`~` の展開・`..` の解決・末尾の `/` の除去をした絶対パスにする。"""
    raise NotImplementedError
