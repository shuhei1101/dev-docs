"""YAML の読み込みと往復編集の読み書き。"""

from __future__ import annotations

from typing import Any

from ruamel.yaml.comments import CommentedMap

YAML_WIDTH = 4096
YAML_INDENT = {"mapping": 2, "sequence": 4, "offset": 2}


class YamlLoadError(ValueError):
    """YAML として読めないことを、ファイル・行・列・理由で表す。"""

    def __init__(
        self,
        reason: str,
        *,
        file: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(reason)
        self.file = file
        self.line = line
        self.column = column
        self.reason = reason


def load_yaml(text: str, *, file: str | None = None) -> Any:
    """YAML の文字列を素の値で読む。"""
    raise NotImplementedError


def load_roundtrip(text: str, *, file: str | None = None) -> CommentedMap:
    """コメントと順序を保つ往復編集の形で YAML を読む。"""
    raise NotImplementedError


def dump_roundtrip(doc: CommentedMap) -> str:
    """往復編集の値を、コメント・順序・字下げを保って文字列にする。"""
    raise NotImplementedError
