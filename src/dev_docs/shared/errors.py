"""開発ドキュメントサーバーのエラーの階層。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class Violation:
    """違反 1 件の項目のパス・決まり・直し方。"""

    path: str
    rule: str
    fix: str = ""
    index: int | None = None


@dataclass(kw_only=True)
class DevDocsError(Exception):
    """MCP の isError と画面の problem+json に変換するエラーの基底。"""

    message: str = ""
    next_steps: list[str] = field(default_factory=list)

    def details(self) -> dict[str, Any]:
        """子クラスが持つ追加のプロパティを辞書で返す。"""
        raise NotImplementedError


@dataclass(kw_only=True)
class UnknownSourceError(DevDocsError):
    """無い配信元。"""

    source_id: str = ""


@dataclass(kw_only=True)
class SourceNotReadableError(DevDocsError):
    """読めない配信元。"""

    available: list[Any] = field(default_factory=list)


@dataclass(kw_only=True)
class SourceNotWritableError(DevDocsError):
    """書き込めない配信元。"""

    available: list[Any] = field(default_factory=list)


@dataclass(kw_only=True)
class SourceNotServedError(DevDocsError):
    """配信していない配信元。"""

    violations: list[Violation] = field(default_factory=list)
    disabled: bool = False


@dataclass(kw_only=True)
class WorktreeNotMatchedError(DevDocsError):
    """ワークツリーに当たらない。"""

    given: str = ""
    patterns: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class TargetIsCloneError(DevDocsError):
    """書く先がクローン本体。"""

    clone: str = ""


@dataclass(kw_only=True)
class InvalidArgumentError(DevDocsError):
    """引数の誤り。"""

    violations: list[Violation] = field(default_factory=list)


@dataclass(kw_only=True)
class RefNotFoundError(DevDocsError):
    """無いリビジョン。"""

    argument: str = ""
    value: str = ""


@dataclass(kw_only=True)
class UnknownKindError(DevDocsError):
    """知らない種類。"""

    kinds: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DocumentNotFoundError(DevDocsError):
    """無い文書。"""

    missing: list[str] = field(default_factory=list)
    candidates: dict[str, list[str]] = field(default_factory=dict)


@dataclass(kw_only=True)
class ValidationFailedError(DevDocsError):
    """検査の不合格。"""

    violations: list[Violation] = field(default_factory=list)


@dataclass(kw_only=True)
class VersionMismatchError(DevDocsError):
    """バージョンの不一致。"""

    doc_id: str = ""
    current: str = ""
    diff: str = ""


@dataclass(kw_only=True)
class DocumentReferencedError(DevDocsError):
    """参照されている。"""

    doc_id: str = ""
    referrers: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DeleteNotAllowedError(DevDocsError):
    """削除を許していない種類。"""

    kind: str = ""


@dataclass(kw_only=True)
class LastReadNotFoundError(DevDocsError):
    """前回読んだ記録が無い。"""


@dataclass(kw_only=True)
class CrossOriginError(DevDocsError):
    """別のオリジンからの要求。"""
