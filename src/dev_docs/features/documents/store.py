"""文書のキャッシュと ID の引き当て。"""

from __future__ import annotations

import difflib
import logging
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from dev_docs.features.access.types import Target
from dev_docs.features.documents.aliases import collect_aliases
from dev_docs.features.documents.fields import missing_ref_fields
from dev_docs.features.documents.loader import collect_files, load_file, unindexed_files
from dev_docs.features.documents.schema import resolve_schema_refs
from dev_docs.features.documents.types import Document, LoadProblem, LoadResult, SyncReport
from dev_docs.features.history.query import file_dates, resolve_ref
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.history.types import FileDates
from dev_docs.features.sources.types import DocumentTable, ServedSource
from dev_docs.integrations.git import GitError, run_git
from dev_docs.shared.errors import DocumentNotFoundError
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

logger = logging.getLogger(__name__)

CANDIDATE_COUNT = 5
CANDIDATE_CUTOFF = 0.6

__all__ = [
    "CANDIDATE_COUNT",
    "CANDIDATE_CUTOFF",
    "DocumentStore",
    "check_sync",
    "collect_files",
    "load_file",
]


def not_found_error(source_id: str, missing: list[str], known: list[str]) -> DocumentNotFoundError:
    """無い ID ごとに近い ID を添えた `DocumentNotFoundError` を作る。"""
    return DocumentNotFoundError(
        message=f"{source_id}: 文書 {', '.join(missing)} はありません",
        missing=missing,
        candidates={
            document_id: difflib.get_close_matches(
                document_id, known, n=CANDIDATE_COUNT, cutoff=CANDIDATE_CUTOFF
            )
            for document_id in missing
        },
        next_steps=["search_docs で ID を探してください"],
    )


type _BodyStamps = tuple[tuple[str, int, int], ...]
type _CachedFile = tuple[int, int, list[Document], list[LoadProblem], _BodyStamps]


def _body_stamps(root: Path, documents: Sequence[Document]) -> _BodyStamps:
    """文書が指す本文のファイルの (パス, 更新日時, 大きさ) を、パスの順に返す。"""
    stamps: list[tuple[str, int, int]] = []
    for path in sorted({d.body_path for d in documents if d.body_path is not None}):
        try:
            stat = (root / path).stat()
        except OSError:
            continue
        stamps.append((path, stat.st_mtime_ns, stat.st_size))
    return tuple(stamps)


class DocumentStore:
    """読む場所ごとに文書を集め、ファイルごとに結果をキャッシュする。"""

    def __init__(self, snapshots: SnapshotStore) -> None:
        self.snapshots = snapshots
        self._files: dict[tuple[Path, str], _CachedFile] = {}
        self._schemas: dict[Path, tuple[int, int, dict[str, Any]]] = {}
        self._dates: dict[tuple[Path, str], dict[str, FileDates]] = {}
        self._lock = threading.Lock()

    def read_root(self, target: Target) -> Path:
        """読むフォルダを決める（`ref` があればリビジョンを書き出す）。"""
        if target.ref is None:
            return target.base
        source = target.source
        repo_root = source.repo_root or source.root
        resolved = resolve_ref(repo_root, target.ref, date_base=source.config.default_ref)
        checkout = self.snapshots.checkout(repo_root, resolved.commit)
        return checkout / source.root.relative_to(repo_root)

    def location(self, target: Target, document: Document) -> str | None:
        """文書のファイルの絶対パスを返す（リビジョンを読んだ文書は `None`）。"""
        if target.ref is not None:
            return None
        return str(self.read_root(target) / (document.body_path or document.path))

    def _file_dates(self, target: Target) -> dict[str, FileDates]:
        """Git の配信元のファイルの日時を、配信元の直下からのパスで返す。"""
        source = target.source
        if not source.is_git:
            return {}
        repo_root = source.repo_root or source.root
        work_root = target.worktree or repo_root
        try:
            if target.ref is not None:
                commit = resolve_ref(
                    repo_root, target.ref, date_base=source.config.default_ref
                ).commit
            else:
                output = run_git(["rev-parse", "HEAD"], cwd=work_root)
                commit = (output if isinstance(output, str) else output.decode("utf-8")).strip()
        except GitError:
            # commit がまだ 1 つも無いリポジトリ
            return {}
        key = (work_root, commit)
        with self._lock:
            cached = self._dates.get(key)
        if cached is None:
            prefix = source.root.relative_to(repo_root).as_posix()
            raw = file_dates(work_root, commit=commit)
            cached = {
                path if prefix == "." else path.removeprefix(f"{prefix}/"): dates
                for path, dates in raw.items()
                if prefix == "." or path.startswith(f"{prefix}/")
            }
            with self._lock:
                self._dates[key] = cached
        return cached

    def _tables(self, target: Target, kinds: Sequence[str] | None) -> list[DocumentTable]:
        """読む文書の行を決める。"""
        source = target.source
        if kinds is not None:
            return [source.table(kind) for kind in kinds]
        return [row for row in source.config.documents if row.enabled]

    def _load_table(
        self, root: Path, table: DocumentTable, source_id: str, dates: dict[str, FileDates]
    ) -> tuple[list[Document], list[LoadProblem], set[tuple[Path, str]]]:
        """1 つの文書の行のファイルを集め、変わったファイルだけ読み直す。"""
        documents: list[Document] = []
        problems: list[LoadProblem] = []
        seen: set[tuple[Path, str]] = set()
        for path in collect_files(root, table):
            absolute = root / path
            key = (absolute, table.id)
            seen.add(key)
            try:
                stat = absolute.stat()
            except OSError:
                continue
            with self._lock:
                cached = self._files.get(key)
            if (
                cached is not None
                and cached[:2] == (stat.st_mtime_ns, stat.st_size)
                and not any(issue.reason == "missing_body_file" for issue in cached[3])
                and cached[4] == _body_stamps(root, cached[2])
            ):
                found, issues = cached[2], cached[3]
            else:
                found, issues = load_file(root, path, table, source_id=source_id, dates=dates)
                stamps = _body_stamps(root, found)
                with self._lock:
                    self._files[key] = (stat.st_mtime_ns, stat.st_size, found, issues, stamps)
            documents.extend(found)
            problems.extend(issues)
        return documents, problems, seen

    def load(self, target: Target, *, kinds: Sequence[str] | None = None) -> LoadResult:
        """読む場所の文書を、文書の行ごとに集めて返す。"""
        root = self.read_root(target)
        tables = self._tables(target, kinds)
        dates = self._file_dates(target)
        documents: list[Document] = []
        problems: list[LoadProblem] = []
        kind_ids = {table.id for table in tables}
        seen_keys: set[tuple[Path, str]] = set()
        for table in tables:
            found, issues, seen = self._load_table(root, table, target.source.id, dates)
            documents.extend(found)
            problems.extend(issues)
            seen_keys |= seen
        # 削除されたファイルのキャッシュを捨てる
        with self._lock:
            for key in [
                key
                for key in self._files
                if key[1] in kind_ids and key not in seen_keys and key[0].is_relative_to(root)
            ]:
                del self._files[key]
        first: dict[str, Document] = {}
        unique: list[Document] = []
        for document in documents:
            earlier = first.get(document.id)
            if earlier is None:
                first[document.id] = document
                unique.append(document)
            else:
                problems.append(
                    LoadProblem(
                        path=document.path,
                        reason="duplicate_id",
                        detail=f"ID {document.id} は先の文書（{earlier.path}）と重なります",
                    )
                )
        problems.sort(key=lambda problem: problem.path)
        for problem in problems:
            logger.debug("%s: %s: %s", target.source.id, problem.path, problem.reason)
        return LoadResult(documents=unique, problems=problems)

    def get(
        self, target: Target, ids: Sequence[str], *, kinds: Sequence[str] | None = None
    ) -> list[Document]:
        """ID の並びの順に文書を返す。"""
        by_id = {document.id: document for document in self.load(target, kinds=kinds).documents}
        missing = [document_id for document_id in ids if document_id not in by_id]
        if missing:
            raise not_found_error(target.source.id, missing, list(by_id))
        return [by_id[document_id] for document_id in ids]

    def schema(self, target: Target, kind: str) -> dict[str, Any]:
        """読む場所に合わせた種類のスキーマを返す。"""
        source = target.source
        table = source.table(kind)
        startup = source.schemas.get(kind, {})
        base = source.root / table.schema_path
        if target.ref is None and target.worktree is None:
            return resolve_schema_refs(startup, base)
        path = self.read_root(target) / table.schema_path
        try:
            stat = path.stat()
        except OSError:
            return resolve_schema_refs(startup, base)
        with self._lock:
            cached = self._schemas.get(path)
        if cached is not None and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
        try:
            raw = load_yaml(path.read_text(encoding="utf-8"), file=str(path))
        except OSError, UnicodeDecodeError, YamlLoadError:
            return resolve_schema_refs(startup, base)
        if not isinstance(raw, dict):
            return resolve_schema_refs(startup, base)
        resolved = resolve_schema_refs(raw, path)
        with self._lock:
            self._schemas[path] = (stat.st_mtime_ns, stat.st_size, resolved)
        return resolved

    def invalidate(self, paths: Iterable[Path]) -> None:
        """書き込んだファイルのキャッシュを捨てる。"""
        targets = set(paths)
        with self._lock:
            for key in [key for key in self._files if key[0] in targets]:
                del self._files[key]
            for path in [path for path in self._schemas if path in targets]:
                del self._schemas[path]

    def clear(self) -> None:
        """全てのキャッシュを捨てる。"""
        with self._lock:
            self._files.clear()
            self._schemas.clear()
            self._dates.clear()


def check_sync(store: DocumentStore, source: ServedSource) -> SyncReport:
    """配信元の文書を読み、`metadata` の列の欠け・管理用の YAML のずれ・エイリアスのキーの違反を求める。"""
    result = store.load(Target(source, source.root, None, None, "read"))
    missing_refs = [
        f"{document.kind}: {document.id}: {key}（{field}）"
        for document in result.documents
        for key, field in missing_ref_fields(document.data, source.table(document.kind))
    ]
    unindexed: list[str] = []
    for table in source.config.documents:
        if not table.enabled or table.records is None or table.body_file is None:
            continue
        for index_path in collect_files(source.root, table):
            body_paths = {
                document.body_path
                for document in result.documents
                if document.kind == table.id and document.path == index_path and document.body_path
            }
            unindexed.extend(
                f"{table.id}: {path}"
                for path in unindexed_files(source.root, index_path, body_paths, table)
            )
    missing_body_files = [
        f"{problem.path}: {problem.detail}"
        for problem in result.problems
        if problem.reason == "missing_body_file"
    ]
    return SyncReport(
        source_id=source.id,
        missing_refs=missing_refs,
        unindexed_files=unindexed,
        missing_body_files=missing_body_files,
        alias_violations=collect_aliases(source, result.documents).violations,
    )
