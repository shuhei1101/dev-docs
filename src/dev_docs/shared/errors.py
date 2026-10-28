"""開発ドキュメントサーバーのエラーの階層。"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


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
    status: ClassVar[int] = 500

    def __str__(self) -> str:
        return self.message

    @property
    def name(self) -> str:
        """クラスの名前（MCP の本文の先頭と problem+json の type の末尾に出す）。"""
        return type(self).__name__

    def details(self) -> dict[str, Any]:
        """子クラスが持つ追加のプロパティを辞書で返す。"""
        base = {item.name for item in dataclasses.fields(DevDocsError)}
        result: dict[str, Any] = {}
        for item in dataclasses.fields(self):
            if item.name in base:
                continue
            result[item.name] = _plain(getattr(self, item.name))
        return result


def _plain(value: Any) -> Any:
    """違反と権限の dataclass を辞書に、パスを文字列にし、配列と辞書は中身を再帰で直す。"""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    return value


@dataclass(kw_only=True)
class UnknownSourceError(DevDocsError):
    """無い配信元。"""

    status: ClassVar[int] = 404
    source_id: str = ""


@dataclass(kw_only=True)
class SourceNotReadableError(DevDocsError):
    """読めない配信元。"""

    status: ClassVar[int] = 403
    available: list[Any] = field(default_factory=list)


@dataclass(kw_only=True)
class SourceNotWritableError(DevDocsError):
    """書き込めない配信元。"""

    status: ClassVar[int] = 403
    available: list[Any] = field(default_factory=list)


@dataclass(kw_only=True)
class SourceNotServedError(DevDocsError):
    """配信していない配信元。"""

    status: ClassVar[int] = 404
    violations: list[Violation] = field(default_factory=list)
    disabled: bool = False


@dataclass(kw_only=True)
class WorktreeNotMatchedError(DevDocsError):
    """ワークツリーに当たらない。"""

    status: ClassVar[int] = 400
    given: str = ""
    patterns: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class TargetIsCloneError(DevDocsError):
    """書く先がクローン本体。"""

    status: ClassVar[int] = 409
    clone: str = ""


@dataclass(kw_only=True)
class InvalidArgumentError(DevDocsError):
    """引数の誤り。"""

    status: ClassVar[int] = 400
    violations: list[Violation] = field(default_factory=list)


@dataclass(kw_only=True)
class RefNotFoundError(DevDocsError):
    """無いリビジョン。"""

    status: ClassVar[int] = 404
    argument: str = ""
    value: str = ""


@dataclass(kw_only=True)
class UnknownKindError(DevDocsError):
    """知らない種類。"""

    status: ClassVar[int] = 400
    kinds: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DocumentNotFoundError(DevDocsError):
    """無い文書。"""

    status: ClassVar[int] = 404
    missing: list[str] = field(default_factory=list)
    candidates: dict[str, list[str]] = field(default_factory=dict)


@dataclass(kw_only=True)
class ValidationFailedError(DevDocsError):
    """検査の不合格。"""

    status: ClassVar[int] = 422
    violations: list[Violation] = field(default_factory=list)


@dataclass(kw_only=True)
class VersionMismatchError(DevDocsError):
    """バージョンの不一致。"""

    status: ClassVar[int] = 409
    doc_id: str = ""
    current: str = ""
    diff: str = ""


@dataclass(kw_only=True)
class DocumentReferencedError(DevDocsError):
    """参照されている。"""

    status: ClassVar[int] = 409
    doc_id: str = ""
    referrers: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DeleteNotAllowedError(DevDocsError):
    """削除を許していない種類。"""

    status: ClassVar[int] = 403
    kind: str = ""


@dataclass(kw_only=True)
class LastReadNotFoundError(DevDocsError):
    """前回読んだ記録が無い。"""

    status: ClassVar[int] = 400


@dataclass(kw_only=True)
class CrossOriginError(DevDocsError):
    """別のオリジンからの要求。"""

    status: ClassVar[int] = 403


@dataclass(kw_only=True)
class ConfigNotFoundError(DevDocsError):
    """配信元の設定が無い。"""

    status: ClassVar[int] = 404
    path: str = ""


@dataclass(kw_only=True)
class ConfigParseError(DevDocsError):
    """配信元の設定が YAML として読めない。"""

    status: ClassVar[int] = 400
    line: int | None = None
    column: int | None = None


@dataclass(kw_only=True)
class ConvertScriptError(DevDocsError):
    """変換スクリプトの失敗。"""

    status: ClassVar[int] = 422
    script: str = ""


@dataclass(kw_only=True)
class RestartInProgressError(DevDocsError):
    """再起動か更新の途中。"""

    status: ClassVar[int] = 409


@dataclass(kw_only=True)
class UpdateFailedError(DevDocsError):
    """更新のコマンドの失敗。"""

    status: ClassVar[int] = 500
    command: list[str] = field(default_factory=list)
    stderr: str = ""
