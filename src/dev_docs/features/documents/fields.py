"""文書の項目のパスの分解と、値の取得。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from dev_docs.integrations.project_index.types import IndexedDocument
from dev_docs.shared.errors import InvalidArgumentError, Violation

METADATA_KEYS = (
    "id",
    "name",
    "description",
    "tags",
    "main_tags",
    "related",
    "status",
    "alias_type",
    "aliases",
    "command",
    "cwd",
    "url",
    "avoid",
    "skill",
    "tool",
    "path",
    "port",
    "replacement",
)

PART_PATTERN = re.compile(r"^([^.\[\]]+)((?:\[(?:\d+|[A-Za-z][A-Za-z0-9_]*)?\])*)$")
INDEX_PATTERN = re.compile(r"\[(\d+|[A-Za-z][A-Za-z0-9_]*)?\]")
PATH_EXAMPLE = "例 `a.b[0].c`・`tags[].name`・`tags[main].name`"


@dataclass(frozen=True, slots=True)
class ArraySelector:
    """項目のパスの `[]`・`[{キー}]` が表す、配列から選ぶ要素。"""

    key: str | None


Token = str | int | ArraySelector


def _invalid(path: str, message: str) -> InvalidArgumentError:
    """項目のパスの誤りを、違反 1 件の `InvalidArgumentError` にする。"""
    return InvalidArgumentError(message=message, violations=[Violation(path=path, rule=message)])


def parse_field_path(path: str) -> list[Token]:
    """ドット記法・`[n]`・`[]`・`[{キー}]` の項目のパスを、キー・位置・要素の選び方の並びにする。"""
    tokens: list[Token] = []
    for part in path.split("."):
        matched = PART_PATTERN.match(part)
        if matched is None:
            raise _invalid(path, f"項目のパス {path} の記載方法が誤っています（{PATH_EXAMPLE}）")
        tokens.append(matched.group(1))
        for inner in INDEX_PATTERN.findall(matched.group(2)):
            if not inner:
                tokens.append(ArraySelector(key=None))
            elif inner.isdecimal():
                tokens.append(int(inner))
            else:
                tokens.append(ArraySelector(key=inner))
    return tokens


def _plain_tokens(path: str, verb: str) -> list[str | int]:
    """要素の選び方を含まないパスを分ける。含めば `InvalidArgumentError` を送る。"""
    tokens = parse_field_path(path)
    if any(isinstance(token, ArraySelector) for token in tokens):
        raise _invalid(path, f"{path}: `[]`・`[{{キー}}]` を含む項目のパス{verb}")
    return [token for token in tokens if not isinstance(token, ArraySelector)]


def _select(data: Any, tokens: Sequence[Token], default: Any) -> Any:
    """要素の選び方を含む並びをたどり、選んだ要素ごとの値の配列にする。"""
    for depth, token in enumerate(tokens):
        if not isinstance(token, ArraySelector):
            continue
        found, current = _walk(data, tokens[:depth])  # type: ignore[arg-type]
        if not found or not isinstance(current, list):
            return default
        rest = tokens[depth + 1 :]
        values: list[Any] = []
        for element in current:
            if token.key is not None and not (
                isinstance(element, Mapping) and element.get(token.key)
            ):
                continue
            if any(isinstance(item, ArraySelector) for item in rest):
                picked = _select(element, rest, None)
                if isinstance(picked, list):
                    values.extend(picked)
                continue
            ok, value = _walk(element, rest)  # type: ignore[arg-type]
            if ok:
                values.append(value)
        return values
    found, value = _walk(data, tokens)  # type: ignore[arg-type]
    return value if found else default


def _walk(data: Any, tokens: Sequence[str | int]) -> tuple[bool, Any]:
    """先頭からたどり、たどれたか・たどり着いた値を返す。"""
    current = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return False, None
            current = current[token]
        else:
            if not isinstance(current, Mapping) or token not in current:
                return False, None
            current = current[token]
    return True, current


def _join(tokens: Sequence[str | int]) -> str:
    """キーと位置の並びを項目のパスの文字列に戻す。"""
    text = ""
    for token in tokens:
        if isinstance(token, int):
            text += f"[{token}]"
        else:
            text += f".{token}" if text else token
    return text


def get_field(data: Mapping[str, Any], path: str, *, default: Any = None) -> Any:
    """項目のパスで指した値を返す。"""
    return _select(data, parse_field_path(path), default)


def is_markdown_body(document: IndexedDocument) -> bool:
    """文書の本文が Markdown のファイルか（`body_path` の拡張子が `.md`）。"""
    return (
        document.body_path is not None and PurePosixPath(document.body_path).suffix.lower() == ".md"
    )
