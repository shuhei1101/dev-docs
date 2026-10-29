"""文書の項目のパスの読み書きと、メタデータの解決。"""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable
from dev_docs.shared.errors import InvalidArgumentError, Violation

METADATA_KEYS = (
    "id",
    "name",
    "description",
    "tags",
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

PART_PATTERN = re.compile(r"^([^.\[\]]+)((?:\[\d+\])*)$")
INDEX_PATTERN = re.compile(r"\[(\d+)\]")


def _invalid(path: str, message: str) -> InvalidArgumentError:
    """項目のパスの誤りを、違反 1 件の `InvalidArgumentError` にする。"""
    return InvalidArgumentError(message=message, violations=[Violation(path=path, rule=message)])


def parse_field_path(path: str) -> list[str | int]:
    """ドット記法と `[n]` の項目のパスをキーと位置の並びにする。"""
    tokens: list[str | int] = []
    for part in path.split("."):
        matched = PART_PATTERN.match(part)
        if matched is None:
            raise _invalid(path, f"項目のパス {path} の書き方が誤っています（例 `a.b[0].c`）")
        tokens.append(matched.group(1))
        tokens.extend(int(index) for index in INDEX_PATTERN.findall(matched.group(2)))
    return tokens


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
    found, value = _walk(data, parse_field_path(path))
    return value if found else default


def set_field(data: MutableMapping[str, Any], path: str, value: Any) -> None:
    """項目のパスで指した場所へ値を書く。"""
    tokens = parse_field_path(path)
    current: Any = data
    for depth, token in enumerate(tokens[:-1]):
        following = tokens[depth + 1]
        if isinstance(token, int):
            if not isinstance(current, list):
                raise _invalid(path, f"{path}: {_join(tokens[:depth])} は配列ではありません")
            if token > len(current):
                raise _invalid(
                    path, f"{path}: 位置 {token} は配列の長さ {len(current)} を超えています"
                )
            if token == len(current):
                current.append([] if isinstance(following, int) else {})
            current = current[token]
        else:
            if not isinstance(current, MutableMapping):
                raise _invalid(path, f"{path}: {_join(tokens[:depth])} は辞書ではありません")
            if token not in current:
                current[token] = [] if isinstance(following, int) else {}
            current = current[token]
    last = tokens[-1]
    if isinstance(last, int):
        if not isinstance(current, list):
            raise _invalid(path, f"{path}: {_join(tokens[:-1])} は配列ではありません")
        if last > len(current):
            raise _invalid(path, f"{path}: 位置 {last} は配列の長さ {len(current)} を超えています")
        if last == len(current):
            current.append(value)
        else:
            current[last] = value
        return
    if not isinstance(current, MutableMapping):
        raise _invalid(path, f"{path}: {_join(tokens[:-1])} は辞書ではありません")
    current[last] = value


def delete_field(data: MutableMapping[str, Any], path: str) -> bool:
    """項目のパスで指した値を削除する。"""
    tokens = parse_field_path(path)
    found, parent = _walk(data, tokens[:-1])
    if not found:
        return False
    last = tokens[-1]
    if isinstance(last, int):
        if not isinstance(parent, list) or last >= len(parent):
            return False
        del parent[last]
        return True
    if not isinstance(parent, MutableMapping) or last not in parent:
        return False
    del parent[last]
    return True


def resolve_metadata(data: Mapping[str, Any], table: DocumentTable) -> dict[str, Any]:
    """文書の行の `metadata` の列名の対応で、文書の内容から共通のキーの値を取る。"""
    result: dict[str, Any] = {}
    for key in METADATA_KEYS:
        value = get_field(data, table.metadata.get(key, key))
        if value is not None:
            result[key] = value
    if table.alias_type is not None:
        result["alias_type"] = table.alias_type
    return result


def missing_ref_fields(data: Mapping[str, Any], table: DocumentTable) -> list[tuple[str, str]]:
    """`metadata` に書いた列のうち、文書の内容に値が無い列を `(キー, 列名)` で返す。"""
    return [
        (key, column) for key, column in table.metadata.items() if get_field(data, column) is None
    ]


def is_markdown_body(document: Document) -> bool:
    """文書の本文が Markdown のファイルか（`body_path` の拡張子が `.md`）。"""
    return (
        document.body_path is not None and PurePosixPath(document.body_path).suffix.lower() == ".md"
    )
