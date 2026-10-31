"""変換の選択と `converters[]` の実行。"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from dev_docs.features.access.types import Target, script_at
from dev_docs.features.convert.embed import EMBED_PATTERN, expand_embeds
from dev_docs.features.convert.markdown import schema_to_markdown
from dev_docs.features.convert.types import Converted, ConvertFailure
from dev_docs.features.documents.fields import is_markdown_body
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.integrations.scripts import (
    ScriptError,
    ScriptFailedError,
    ScriptTimeoutError,
    run_script,
)
from dev_docs.shared.files import replace_file
from dev_docs.shared.hashing import value_hash
from dev_docs.shared.version import RUNNING_VERSION

logger = logging.getLogger(__name__)

TABLE_KEY_PATTERN = r"^<!-- dev-docs-table: (?P<key>.+) -->$"
CONVERT_CACHE_KEEP = 2000

TABLE_DATA_MARKER = "<!-- table: data -->"
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
FENCE = re.compile(r"^\s{0,3}(?P<mark>`{3,}|~{3,})")

__all__ = ["CONVERT_CACHE_KEEP", "TABLE_KEY_PATTERN", "ConvertService", "run_script"]


def _strip_table_keys(markdown: str, kind: str) -> tuple[str, list[str]]:
    """表のキーのマーカーを取り除き、本文の表を出る順に表のキーと並べる。"""
    key_pattern = re.compile(TABLE_KEY_PATTERN)
    lines = markdown.splitlines(keepends=True)
    kept: list[str] = []
    keys: list[str] = []
    fence: str | None = None
    pending: str | None = None
    in_table = False
    for index, line in enumerate(lines):
        text = line.rstrip("\r\n")
        opened = FENCE.match(line)
        if fence is None and opened:
            fence = opened.group("mark")
            pending, in_table = None, False
        elif fence is not None:
            if (
                opened
                and opened.group("mark")[0] == fence[0]
                and len(opened.group("mark")) >= len(fence)
            ):
                fence = None
        else:
            matched = key_pattern.match(text)
            if matched:
                pending = matched.group("key")
                continue
            is_row = text.lstrip().startswith("|")
            if is_row and not in_table:
                following = lines[index + 1].rstrip("\r\n") if index + 1 < len(lines) else ""
                if SEPARATOR_ROW.match(following):
                    keys.append(pending or f"{kind}:table[{len(keys)}]")
                    pending, in_table = None, True
            elif not is_row:
                in_table = False
                if text.strip() and text != TABLE_DATA_MARKER:
                    pending = None
        kept.append(line)
    return "".join(kept), keys


class ConvertService:
    """文書の行の設定で変換を選び、埋め込みを展開した Markdown を返す。"""

    def __init__(self, cache_dir: Path, store: DocumentStore, timeout_sec: float) -> None:
        self.cache_dir = cache_dir
        self.store = store
        self.timeout_sec = timeout_sec

    def _cache_path(
        self, target: Target, document: Document, converter: str, run: list[str]
    ) -> Path:
        """`converters[]` の結果の控えのファイルを返す。"""
        # dev-docs が持つ変換（`dev-docs prompt-doc`）の出力は dev-docs の更新で変わるため、バージョンも含める
        parts = (
            target.source.id,
            document.kind,
            converter,
            document.version,
            value_hash(run),
            RUNNING_VERSION,
        )
        name = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / f"{name}.md"

    def _prune(self) -> None:
        """控えが `CONVERT_CACHE_KEEP` を超えたら、更新日時が古いものから消す。"""
        files = [item for item in self.cache_dir.glob("*.md") if item.is_file()]
        excess = len(files) - CONVERT_CACHE_KEEP
        if excess <= 0:
            return
        for item in sorted(files, key=lambda file: file.stat().st_mtime)[:excess]:
            item.unlink(missing_ok=True)

    def _run_converter(
        self, target: Target, document: Document, converter: str
    ) -> str | ConvertFailure:
        """`converters[]` のスクリプトで Markdown にする（控えがあればそれを使う）。"""
        entry = target.source.script("converters", converter)
        cache = self._cache_path(target, document, converter, entry.run)
        if cache.is_file():
            return cache.read_text(encoding="utf-8")
        script = " ".join(entry.run)
        try:
            result = run_script(
                entry.run,
                cwd=target.base,
                stdin=document.body,
                timeout_sec=self.timeout_sec,
                at=script_at(target),
            )
        except ScriptTimeoutError:
            return ConvertFailure(
                reason="timeout",
                kind=document.kind,
                script=script,
                detail=f"{self.timeout_sec:g} 秒",
            )
        except ScriptFailedError as error:
            return ConvertFailure(
                reason="exit", kind=document.kind, script=script, detail=error.reason
            )
        except ScriptError as error:
            return ConvertFailure(
                reason="not_runnable", kind=document.kind, script=script, detail=error.reason
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        replace_file(cache, result.stdout)
        self._prune()
        return result.stdout

    def convert(self, target: Target, document: Document) -> Converted:
        """1 件の文書を Markdown にする。"""
        table = target.source.table(document.kind)
        if table.converter is not None:
            produced = self._run_converter(target, document, table.converter)
            if isinstance(produced, ConvertFailure):
                return Converted(markdown="", failure=produced)
            markdown = produced
        elif is_markdown_body(document):
            markdown = document.body
        else:
            markdown = schema_to_markdown(document, self.store.row_schema(target, document.kind))
        # ref を読むときだけ、埋め込みのマーカーがあればそのリビジョンを取り出した場所から読む
        base = target.base
        if target.ref is not None and re.search(EMBED_PATTERN, markdown):
            base = self.store.read_root(target)
        stripped, keys = _strip_table_keys(expand_embeds(markdown, base), document.kind)
        return Converted(markdown=stripped, table_keys=keys)

    def clear(self) -> None:
        """`cache_dir` の控えを全て消す。"""
        if not self.cache_dir.is_dir():
            return
        for item in self.cache_dir.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
