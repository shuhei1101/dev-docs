"""パスの正規化。"""

from __future__ import annotations

import os
from pathlib import Path


def normalize_path(path: str | Path) -> Path:
    """`~` の展開・`..` の解決・末尾の `/` の除去をした絶対パスにする。"""
    return Path(os.path.abspath(Path(path).expanduser()))
