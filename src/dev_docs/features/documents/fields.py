"""文書の項目のパスの読み書きと、メタデータの解決。"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from dev_docs.features.sources.types import DocumentDefaults, DocumentTable

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
UNION_KEYS = ("tags", "related")


def parse_field_path(path: str) -> list[str | int]:
    """ドット記法と `[n]` の項目のパスをキーと位置の並びにする。"""
    raise NotImplementedError


def get_field(data: Mapping[str, Any], path: str, *, default: Any = None) -> Any:
    """項目のパスで指した値を返す。"""
    raise NotImplementedError


def set_field(data: MutableMapping[str, Any], path: str, value: Any) -> None:
    """項目のパスで指した場所へ値を書く。"""
    raise NotImplementedError


def delete_field(data: MutableMapping[str, Any], path: str) -> bool:
    """項目のパスで指した値を削除する。"""
    raise NotImplementedError


def resolve_metadata(data: Mapping[str, Any], table: DocumentTable) -> dict[str, Any]:
    """文書の行の `metadata` の対応で、文書の内容から共通のキーの値を取る。"""
    raise NotImplementedError


def apply_defaults(
    metadata: Mapping[str, Any], defaults: Sequence[DocumentDefaults], path: str
) -> dict[str, Any]:
    """`defaults[]` のうちパスの当たる行を上から重ね、最後に文書自身のメタデータを重ねる。"""
    raise NotImplementedError
