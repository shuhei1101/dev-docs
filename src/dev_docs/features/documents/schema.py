"""種類のスキーマの `$ref` の解決。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urldefrag

from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

logger = logging.getLogger(__name__)


class _Unresolved(Exception):
    """`$ref` の参照先が無い・読めないことを表す。"""


def _file_schema(path: Path, cache: dict[Path, Any]) -> Any:
    """参照先のスキーマのファイルを読む（同じファイルは 1 回だけ読む）。"""
    if path not in cache:
        try:
            cache[path] = load_yaml(path.read_text(encoding="utf-8"), file=str(path))
        except (OSError, UnicodeDecodeError, YamlLoadError) as error:
            raise _Unresolved(str(error)) from error
    return cache[path]


def _pointer(document: Any, fragment: str) -> Any:
    """JSON Pointer（`/$defs/x`）でたどる。"""
    current = document
    for raw in [part for part in fragment.split("/") if part]:
        key = unquote(raw).replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError) as error:
                raise _Unresolved(f"{fragment} がありません") from error
        elif isinstance(current, Mapping) and key in current:
            current = current[key]
        else:
            raise _Unresolved(f"{fragment} がありません")
    return current


def resolve_schema_refs(schema: Mapping[str, Any], base: Path) -> dict[str, Any]:
    """種類のスキーマの `$ref` を参照先の中身で置き換えたスキーマを返す。"""
    files: dict[Path, Any] = {}

    def resolve(value: Any, current: Path, document: Any, stack: tuple[str, ...]) -> Any:
        if isinstance(value, list):
            return [resolve(item, current, document, stack) for item in value]
        if not isinstance(value, Mapping):
            return value
        ref = value.get("$ref")
        if not isinstance(ref, str):
            # 最上位の `$defs` は参照先として使うので、そのまま残す
            return {
                key: item
                if key == "$defs" and not stack
                else resolve(item, current, document, stack)
                for key, item in value.items()
            }
        location, fragment = urldefrag(ref)
        target_path = current if not location else (current.parent / unquote(location))
        identity = f"{target_path}#{fragment}"
        if identity in stack:
            logger.warning("スキーマの循環する参照を解かずに残した（%s・%s）", current, ref)
            return dict(value)
        try:
            target_doc = document if not location else _file_schema(target_path.resolve(), files)
            target = _pointer(target_doc, fragment)
        except _Unresolved as error:
            logger.warning("スキーマの参照を解けなかった（%s・%s・%s）", current, ref, error)
            return dict(value)
        resolved = resolve(target, target_path, target_doc, (*stack, identity))
        if not isinstance(resolved, dict):
            return resolved
        extra = {
            key: resolve(item, current, document, stack)
            for key, item in value.items()
            if key != "$ref"
        }
        return {**resolved, **extra}

    result = resolve(schema, base, schema, ())
    return result  # type: ignore[no-any-return]
