"""文書のファイルの収集と読み込み。"""

from __future__ import annotations

import os
import posixpath
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path, PurePosixPath
from typing import Any

from dev_docs.features.documents.fields import apply_defaults, get_field, resolve_metadata
from dev_docs.features.documents.types import Document, LoadProblem
from dev_docs.features.history.types import FileDates
from dev_docs.features.sources.types import DocumentTable
from dev_docs.shared.hashing import content_hash, value_hash
from dev_docs.shared.yaml_io import YamlLoadError, dump_roundtrip, load_yaml

SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv"})
FRONT_MATTER_FENCE = "---"


def collect_files(root: Path, patterns: Sequence[str]) -> list[str]:
    """文書の行の `paths` に当たるファイルを配信元の直下から集める。"""
    found: set[str] = set()
    for folder, dirnames, filenames in os.walk(root):
        # シンボルリンクのフォルダは中をたどらない
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIP_DIRS and not os.path.islink(os.path.join(folder, name))
        ]
        relative_folder = Path(folder).relative_to(root).as_posix()
        for name in filenames:
            relative = name if relative_folder == "." else f"{relative_folder}/{name}"
            target = PurePosixPath(relative)
            if any(target.full_match(pattern) for pattern in patterns):
                found.add(relative)
    return sorted(found)


def split_front_matter(text: str, *, file: str | None = None) -> tuple[dict[str, Any], str]:
    """Markdown の先頭の front matter と本文を分ける。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != FRONT_MATTER_FENCE:
        return {}, text
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip() == FRONT_MATTER_FENCE),
        None,
    )
    if closing is None:
        return {}, text
    try:
        data = load_yaml("".join(lines[1:closing]), file=file)
    except YamlLoadError as error:
        # 行はファイル全体の中の位置にする（開きの `---` の 1 行を足す）
        line = error.line + 1 if error.line else None
        raise YamlLoadError(
            error.reason, file=error.file, line=line, column=error.column
        ) from error
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise YamlLoadError("front matter が辞書ではありません", file=file)
    return data, "".join(lines[closing + 1 :])


def _as_datetime(value: Any) -> datetime | None:
    """ISO 8601 の文字列・日時・日付を日時にする。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        # 日付だけの値は、その日の 0 時（端末のタイムゾーン）にする
        return datetime.combine(value, time.min).astimezone()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _timestamps(data: Mapping[str, Any], key: str, file_dates: FileDates | None) -> datetime | None:
    """git の日時、無ければ内容の項目の日時を返す。"""
    if file_dates is not None:
        return file_dates.created if key == "created" else file_dates.updated
    return _as_datetime(data.get(key))


def _body_file(root: Path, path: str, value: Any) -> tuple[str, str] | None:
    """`body_file` が指すファイルの `root` からのパスと内容を返す（無い・外を指すなら `None`）。"""
    if not isinstance(value, str) or not value:
        return None
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(path), value))
    if relative == ".." or relative.startswith(("../", "/")):
        return None
    target = root / relative
    try:
        if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
            return None
        return relative, target.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return None


def _stem(path: str) -> str:
    """パスから拡張子を除く。"""
    return posixpath.splitext(path)[0]


def _build(
    *,
    data: dict[str, Any],
    body: str,
    body_path: str | None,
    index: int | None,
    version: str,
    path: str,
    table: DocumentTable,
    source_id: str,
    dates: Mapping[str, FileDates],
    fallback_id: str,
) -> Document:
    """内容・本文・バージョンから 1 件の文書を作る。"""
    key_path = body_path or path
    metadata = apply_defaults(resolve_metadata(data, table), table.defaults, key_path)
    document_id = metadata.get("id")
    file_dates = dates.get(key_path)
    return Document(
        id=str(document_id) if document_id is not None else fallback_id,
        kind=table.id,
        source_id=source_id,
        path=path,
        record_index=index,
        data=data,
        body=body,
        body_path=body_path,
        metadata=metadata,
        version=version,
        created=_timestamps(data, "created", file_dates),
        updated=_timestamps(data, "updated", file_dates),
    )


def documents_from_text(
    text: str,
    root: Path,
    path: str,
    table: DocumentTable,
    *,
    source_id: str,
    dates: Mapping[str, FileDates] | None = None,
) -> tuple[list[Document], list[LoadProblem]]:
    """1 つのファイルの内容の文字列を、文書の行に従って 1 件以上の文書にする。"""
    dates = dates or {}
    common: dict[str, Any] = {"path": path, "table": table, "source_id": source_id, "dates": dates}
    try:
        if table.type == "markdown":
            data, body = split_front_matter(text, file=path)
            return [
                _build(
                    data=data,
                    body=body,
                    body_path=None,
                    index=None,
                    version=content_hash(text),
                    fallback_id=_stem(path),
                    **common,
                )
            ], []
        loaded = load_yaml(text, file=path)
    except YamlLoadError as error:
        return [], [LoadProblem(path=path, reason="unreadable", detail=str(error))]
    if table.records is None:
        if not isinstance(loaded, dict):
            return [], [
                LoadProblem(path=path, reason="not_mapping", detail="最上位が辞書ではありません")
            ]
        return [
            _build(
                data=loaded,
                body=text,
                body_path=None,
                index=None,
                version=content_hash(text),
                fallback_id=_stem(path),
                **common,
            )
        ], []
    if not isinstance(loaded, dict):
        return [], [
            LoadProblem(path=path, reason="not_mapping", detail="最上位が辞書ではありません")
        ]
    records = get_field(loaded, table.records)
    documents: list[Document] = []
    problems: list[LoadProblem] = []
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            problems.append(
                LoadProblem(
                    path=path,
                    reason="not_mapping",
                    detail=f"{table.records}[{index}] が辞書ではありません",
                )
            )
            continue
        body_path: str | None = None
        if table.body_file is not None:
            value = get_field(record, table.body_file)
            found = _body_file(root, path, value)
            if found is None:
                problems.append(
                    LoadProblem(
                        path=path,
                        reason="missing_body_file",
                        detail=f"{table.records}[{index}] の {table.body_file}（{value}）が指すファイルがありません",
                    )
                )
                continue
            body_path, body = found
            fallback_id = _stem(body_path)
        else:
            body = dump_roundtrip(record)  # type: ignore[arg-type]
            fallback_id = f"{_stem(path)}#{index}"
        documents.append(
            _build(
                data=record,
                body=body,
                body_path=body_path,
                index=index,
                version=value_hash(record),
                fallback_id=fallback_id,
                **common,
            )
        )
    return documents, problems


def load_file(
    root: Path,
    path: str,
    table: DocumentTable,
    *,
    source_id: str,
    dates: Mapping[str, FileDates] | None = None,
) -> tuple[list[Document], list[LoadProblem]]:
    """1 つのファイルを読み、文書の行に従って 1 件以上の文書にする。"""
    try:
        text = (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [], [LoadProblem(path=path, reason="unreadable", detail=str(error))]
    return documents_from_text(text, root, path, table, source_id=source_id, dates=dates)
