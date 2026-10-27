"""リビジョンの解決・一覧・変わったファイル・ファイルの日時。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dev_docs.features.history.types import FileChange, FileDates, RefList, ResolvedRef
from dev_docs.features.sources.types import ServedSource

SHORT_SHA_LENGTH = 7
CO_CHANGE_COMMITS = 50


def resolve_ref(repo_root: Path, ref: str, *, date_base: str, argument: str = "ref") -> ResolvedRef:
    """ブランチ・タグ・commit・日時を commit とその日時に解く。"""
    raise NotImplementedError


def list_refs(source: ServedSource, *, commits: int = 20) -> RefList:
    """配信元のブランチ・タグ・`default_ref` の最近の commit を返す。"""
    raise NotImplementedError


def changed_files(
    work_root: Path,
    from_commit: str,
    to_commit: str | None = None,
    *,
    pathspec: str | None = None,
) -> list[FileChange]:
    """2 つの commit の間、または commit と作業ツリーの間で変わったファイルを返す。"""
    raise NotImplementedError


def file_dates(
    work_root: Path, *, commit: str = "HEAD", pathspec: str | None = None
) -> dict[str, FileDates]:
    """ファイルごとに最初と最後の commit の日時を 1 回の git で引く。"""
    raise NotImplementedError


def co_changed_files(
    work_root: Path, paths: Sequence[str], *, max_commits: int = CO_CHANGE_COMMITS
) -> dict[str, int]:
    """起点のファイルと同じ commit で変わったファイルを、一緒に変わった回数で数える。"""
    raise NotImplementedError


def read_file_at(work_root: Path, commit: str, path: str) -> str | None:
    """commit のあるファイルを書き出さずに読む。"""
    raise NotImplementedError
