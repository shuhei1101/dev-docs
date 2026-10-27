"""新しい文書の置き場所。"""

from __future__ import annotations

import re

from dev_docs.features.sources.types import DocumentTable
from dev_docs.shared.errors import InvalidArgumentError, Violation

GLOB_CHARS = re.compile(r"[*?\[]")
RECURSIVE = "**/"


def _undecided(table: DocumentTable) -> InvalidArgumentError:
    """置き場所を決められないエラーを作る（添字は書き込みが付ける）。"""
    return InvalidArgumentError(
        message=f"{table.id} の新しい文書の置き場所を決められません",
        violations=[
            Violation(
                path="kind",
                rule=f"{table.id} の新しい文書の置き場所を決められません",
                fix="documents[].paths の先頭を glob にしてください",
            )
        ],
    )


def new_document_path(table: DocumentTable, doc_id: str) -> tuple[str, bool]:
    """`create` の文書を書くファイルを、文書の行の `paths` の先頭から決める。"""
    first = table.paths[0] if table.paths else ""
    has_glob = bool(GLOB_CHARS.search(first))
    if table.records is not None:
        if has_glob or not first:
            raise _undecided(table)
        return first, True
    if not has_glob:
        raise _undecided(table)
    folder, _, name = first.rpartition("/")
    folder = folder.replace(RECURSIVE, "").removesuffix("/**")
    # 最後の段の `*` を ID に置き換える
    filename = name.replace("*", doc_id, 1)
    if GLOB_CHARS.search(filename):
        raise _undecided(table)
    folder = "/".join(part for part in folder.split("/") if not GLOB_CHARS.search(part))
    return (f"{folder}/{filename}" if folder else filename), False
