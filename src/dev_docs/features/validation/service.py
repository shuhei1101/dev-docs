"""文書の検査をまとめて通す。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Literal

from dev_docs.features.access.types import Target
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.validation.rules import (
    check_id_format,
    check_related,
    check_schema,
    check_tags,
)
from dev_docs.features.validation.scripts import parse_validator_output
from dev_docs.integrations.scripts import ScriptError, run_script
from dev_docs.shared.errors import Violation

VALIDATOR_ON_READ_CACHE = 4096

__all__ = ["VALIDATOR_ON_READ_CACHE", "DocumentChecker", "run_script"]


class DocumentChecker:
    """1 件の文書に全ての検査を通し、違反をまとめて返す。"""

    def __init__(self, store: DocumentStore, timeout_sec: float) -> None:
        self.store = store
        self.timeout_sec = timeout_sec
        self._read_cache: OrderedDict[tuple[str, str, str, str], list[Violation]] = OrderedDict()
        self._lock = threading.Lock()

    def _run_validator(
        self, target: Target, document: Document, validator_id: str
    ) -> tuple[list[Violation], bool]:
        """検査のスクリプト 1 つを動かし、違反と、動かせたかを返す。"""
        entry = target.source.script("validators", validator_id)
        try:
            result = run_script(
                entry.run,
                cwd=target.base,
                stdin=document.body,
                timeout_sec=self.timeout_sec,
            )
        except ScriptError as error:
            message = " ".join(error.reason.split())
            rule = f"{validator_id}: 検査を実行できませんでした（{message}）"
            return [Violation(path="$", rule=rule)], False
        return parse_validator_output(result.stdout, validator_id=validator_id), True

    def check(
        self,
        target: Target,
        document: Document,
        *,
        on: Literal["read", "write"],
        new: bool = False,
    ) -> list[Violation]:
        """スキーマ・ID の形・関連の種類・タグ・`validators[]` を順に通す。"""
        source = target.source
        table = source.table(document.kind)
        violations: list[Violation] = []
        violations.extend(check_schema(document.data, self.store.schema(target, document.kind)))
        if new:
            violations.extend(
                check_id_format(document.id, source.config.ids_format, kind=document.kind)
            )
        violations.extend(check_related(document.metadata, source.config.related_types))
        violations.extend(check_tags(document.metadata, source.tag_master))
        for validator_id in table.validators:
            entry = source.script("validators", validator_id)
            if on not in entry.on:
                continue
            key = (source.id, document.kind, validator_id, document.version)
            if on == "read":
                with self._lock:
                    cached = self._read_cache.get(key)
                    if cached is not None:
                        self._read_cache.move_to_end(key)
                if cached is not None:
                    violations.extend(cached)
                    continue
            found, ran = self._run_validator(target, document, validator_id)
            violations.extend(found)
            # 動かせなかった結果は控えない
            if on == "read" and ran:
                with self._lock:
                    self._read_cache[key] = found
                    while len(self._read_cache) > VALIDATOR_ON_READ_CACHE:
                        self._read_cache.popitem(last=False)
        return violations

    def clear(self) -> None:
        """読み取りの結果の控えを捨てる。"""
        with self._lock:
            self._read_cache.clear()
