"""一時ファイルからのファイルの置き換え。"""

from __future__ import annotations

from pathlib import Path


def replace_file(path: Path, content: str) -> None:
    """同じフォルダの一時ファイルに書いてから置き換える。"""
    raise NotImplementedError
