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
    doc: str | None = None


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
    """違反の dataclass を辞書に、パスを文字列にし、配列と辞書は中身を再帰で直す。"""
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
class SourceNotServedError(DevDocsError):
    """配信していない配信元。"""

    status: ClassVar[int] = 404
    violations: list[Violation] = field(default_factory=list)
    disabled: bool = False


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
class DocumentNotFoundError(DevDocsError):
    """無い文書。"""

    status: ClassVar[int] = 404
    missing: list[str] = field(default_factory=list)
    candidates: dict[str, list[str]] = field(default_factory=dict)


@dataclass(kw_only=True)
class CrossOriginError(DevDocsError):
    """別のオリジンからの要求。"""

    status: ClassVar[int] = 403


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


@dataclass(kw_only=True)
class ScreenBuildMissingError(DevDocsError):
    """画面のビルドが無い。"""

    status: ClassVar[int] = 503


@dataclass(kw_only=True)
class ProjectIndexUnreachableError(DevDocsError):
    """project-index につながらない・制限時間を超えた。"""

    status: ClassVar[int] = 503
    address: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            self.message = f"project-index（{self.address}）に接続できませんでした。{self.reason}"
        if not self.next_steps:
            self.next_steps = ["project-index を起動してから、再読み込みしてください。"]


@dataclass(kw_only=True)
class ProjectIndexRejectedError(DevDocsError):
    """project-index が要求を受け付けない（422）。"""

    status: ClassVar[int] = 422
    violations: list[Violation] = field(default_factory=list)


@dataclass(kw_only=True)
class ProjectIndexResponseError(DevDocsError):
    """project-index の想定しない応答。"""

    status: ClassVar[int] = 502
    status_code: int = 0
    summary: str = ""
