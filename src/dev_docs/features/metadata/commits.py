"""画面の編集中の変更を文書の書き込みと削除に変えて、project-index の書き込みの API へ送信する。"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from dev_docs.features.metadata.metadata import key_mapping
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.api_model import ApiModel
from dev_docs.shared.errors import (
    DevDocsError,
    DocumentNotFoundError,
    ProjectIndexTimeoutError,
    RefNotFoundError,
)

__all__ = [
    "EDITABLE_COLUMNS",
    "CommitRequest",
    "CommitResult",
    "ConflictReason",
    "ConflictResult",
    "ConflictScript",
    "Edit",
    "EditError",
    "EditsRejectedError",
    "commit_edits",
    "item_expected_versions",
    "to_conflict",
    "to_operations",
]

logger = logging.getLogger(__name__)

EDITABLE_COLUMNS: Mapping[str, frozenset[str]] = {
    "terms": frozenset({"name", "aliases", "description"}),
    "aliases": frozenset({"name", "aliases"}),
    "tags": frozenset({"tags"}),
    "rules": frozenset({"rule", "paths", "tools"}),
    "files": frozenset({"description"}),
}
# 行の追加・削除を受ける種類
ROW_KINDS = frozenset({"terms", "rules"})
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE = 422
HTTP_BAD_GATEWAY = 502
HTTP_GATEWAY_TIMEOUT = 504
NEXT_STEP_WRITE_API_KINDS = "project-index の端末の設定の sources[].direct_commit.write_api_kinds に種類を追加してください。"
DRY_RUN_MESSAGE = "差分確認"
# project-index が編集を始めたときのコミットを起点に使えないと断ったときの problem+json の title
BASE_COMMIT_UNUSABLE = "BaseCommitUnusableError"
# 衝突したときのスクリプトの標準出力の最後の行を PR の URL とみなす接頭辞
PR_URL_PREFIX = "https://"
NEXT_STEP_RELOAD = "メタデータを再読み込みし、変更が反映されたかを確認してください。"

EditKind = Literal["terms", "aliases", "tags", "rules", "files"]
OperationKind = Literal["write", "delete"]
# 違反の `path` の先頭の、書き込み・削除の 1 件を指す部分
_OPERATION_PATH = re.compile(r"^(writes|deletes)\[(\d+)\]\.?(.*)$")


class Edit(ApiModel):
    """編集中の変更 1 件。"""

    key: str
    kind: EditKind
    op: Literal["update", "add", "delete"]
    doc_id: str
    # 列と文書のキーの対応を参照する種類と、403 の `kinds` を変更へ戻すのに使用する
    doc_kind: str
    # `update`・`delete` で必須（取得した文書のバージョン）
    expected_version: str | None = None
    # `update` で必須（編集を始めたときの項目ごとのバージョンを取得する文書のパス）
    doc_path: str | None = None
    values: dict[str, str | list[str]] = Field(default_factory=dict)


class CommitRequest(ApiModel):
    """直コミットの要求の本文。"""

    edits: list[Edit] = Field(min_length=1)
    message: str | None = None
    dry_run: bool = False
    # 編集を始めたときの既定のブランチのコミット（衝突したときのブランチの起点）
    base_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")

    @model_validator(mode="after")
    def _check(self) -> CommitRequest:
        """`key` の重複・`op` と `kind`・必須・`message` を検証する。"""
        keys = [edit.key for edit in self.edits]
        if len(keys) != len(set(keys)):
            raise ValueError("edits[].key が重複しています")
        for edit in self.edits:
            # 行の追加・削除は用語集と索引だけ
            if edit.op != "update" and edit.kind not in ROW_KINDS:
                raise ValueError(f"{edit.key}: {edit.kind} は行を追加・削除できません")
            # 修正・削除は取得したバージョンと照合する
            if edit.op != "add" and not edit.expected_version:
                raise ValueError(f"{edit.key}: expectedVersion がありません")
            # 修正は編集を始めたときの項目ごとのバージョンを文書のパスで取得する
            if edit.op == "update" and not edit.doc_path:
                raise ValueError(f"{edit.key}: docPath がありません")
        if not self.dry_run and not (self.message or "").strip():
            raise ValueError("message を入力してください")
        return self


class EditResult(ApiModel):
    """変更ごとの結果。"""

    key: str
    status: Literal["created", "updated", "deleted"]
    version: str | None
    diff: str


class CommitInfo(ApiModel):
    """プッシュしたコミット。"""

    sha: str
    branch: str


class ConflictReason(ApiModel):
    """今のブランチで断られた理由 1 件（`key` が `None` は本文全体）。"""

    key: str | None
    reason: str


class ConflictScript(ApiModel):
    """衝突したときのスクリプトの結果。"""

    exit_code: int | None
    timed_out: bool
    pr_url: str | None
    stderr: str


class ConflictResult(ApiModel):
    """衝突して修正をブランチに残したとき（差分確認は残すことになるとき）の結果。"""

    branch: str | None
    base_commit: str
    reasons: list[ConflictReason]
    script: ConflictScript | None


class CommitResult(ApiModel):
    """直コミットの 200 の応答。"""

    applied: bool
    results: list[EditResult]
    commit: CommitInfo | None
    conflict: ConflictResult | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EditError:
    """変更ごとの理由（`key` が `None` は本文全体）。"""

    key: str | None
    reason: str
    path: str | None = None


@dataclass(kw_only=True)
class EditsRejectedError(DevDocsError):
    """状態コードと変更ごとの理由つきの失敗。"""

    status: ClassVar[int] = 400
    status_code: int = HTTP_BAD_REQUEST
    errors: list[EditError] = field(default_factory=list)
    # problem+json の title をクラスの名前から変えるとき（`BaseCommitUnusableError` など）
    problem_title: str | None = None

    @property
    def name(self) -> str:
        """problem+json の title と type の末尾。"""
        return self.problem_title or type(self).__name__

    def http_status(self) -> int:
        """problem+json の状態コード。"""
        return self.status_code

    def details(self) -> dict[str, Any]:
        """problem+json の `errors[]`（値の無い項目は除く）。"""
        return {
            "errors": [
                {
                    key: value
                    for key, value in (
                        ("key", item.key),
                        ("path", item.path),
                        ("reason", item.reason),
                    )
                    if value is not None
                }
                for item in self.errors
            ]
        }


def _checked_values(edit: Edit, metadata: Mapping[str, str] | None) -> dict[str, Any]:
    """元のキーへ戻せる列かを確認し、列のキーと値をそのまま返却する。

    文書の実際のキーへは、project-index の書き込みの API が配信元の設定の行の `metadata` で戻す。
    """
    for column in edit.values:
        # 入れ子のパス・絞り込み: 戻せない
        if key_mapping(metadata, column) is None:
            raise EditsRejectedError(
                message="元のキーへ戻せない列を修正しています",
                status_code=HTTP_BAD_REQUEST,
                errors=[EditError(key=edit.key, path=column, reason="この列は修正できません")],
            )
    return dict(edit.values)


def to_operations(
    edits: list[Edit],
    mappings: Mapping[str, Mapping[str, str]],
    expected_versions: Mapping[str, Mapping[str, str] | str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[OperationKind, int, str]]]:
    """編集中の変更を、共通のキーのままの `writes`・`deletes` と、添字と変更の `key` の対応にする。"""
    writes: list[dict[str, Any]] = []
    deletes: list[dict[str, Any]] = []
    indexes: list[tuple[OperationKind, int, str]] = []
    for edit in edits:
        if edit.op == "delete":
            indexes.append(("delete", len(deletes), edit.key))
            deletes.append({"id": edit.doc_id, "expectedVersion": edit.expected_version})
            continue
        values = _checked_values(edit, mappings.get(edit.doc_kind))
        indexes.append(("write", len(writes), edit.key))
        if edit.op == "update":
            writes.append(
                {
                    "op": "update",
                    "id": edit.doc_id,
                    # 修正した最上位のキーだけの項目ごとのバージョン（同じ文書の別の項目の変更とは衝突しない）か文書の全体のバージョン
                    "expected_version": _expected_version(expected_versions.get(edit.key)),
                    "set": values,
                }
            )
        else:
            writes.append(
                {"op": "create", "id": edit.doc_id, "kind": edit.doc_kind, "data": values}
            )
    return writes, deletes, indexes


def _expected_version(value: Mapping[str, str] | str | None) -> dict[str, str] | str:
    """書き込みの操作の `expected_version`（辞書は複製し、文書の全体のバージョンはそのまま）。"""
    if isinstance(value, str):
        return value
    return dict(value or {})


def _check_columns(edits: list[Edit]) -> None:
    """種類ごとに修正できる列だけかを確認する。"""
    errors = [
        EditError(key=edit.key, path=column, reason="この列は修正できません")
        for edit in edits
        for column in edit.values
        if column not in EDITABLE_COLUMNS[edit.kind]
    ]
    if errors:
        raise EditsRejectedError(
            message="修正できない列があります", status_code=HTTP_BAD_REQUEST, errors=errors
        )


def _key_of(
    indexes: list[tuple[OperationKind, int, str]], kind: object, index: object
) -> str | None:
    """project-index の `results[].kind`（`write`・`delete`）と添字を、変更の `key` に戻す。"""
    target: OperationKind = "delete" if kind == "delete" else "write"
    return next((key for op, position, key in indexes if op == target and position == index), None)


def _violation(
    item: Mapping[str, Any], indexes: list[tuple[OperationKind, int, str]], detail: str
) -> EditError:
    """`errors[]` の 1 件の `path` の先頭（`writes[{添字}]`・`deletes[{添字}]`）を変更の `key` に戻す。"""
    path = str(item.get("path") or "")
    matched = _OPERATION_PATH.match(path)
    # 書き込み・削除の 1 件を指す違反: 変更の `key` と、その中のパス
    if matched:
        kind = "delete" if matched.group(1) == "deletes" else "write"
        key = _key_of(indexes, kind, int(matched.group(2)))
        rest = matched.group(3) or None
    # 本文全体の違反
    else:
        key, rest = None, path or None
    return EditError(key=key, path=rest, reason=str(item.get("reason") or detail))


def _rejected(
    status: int,
    body: Mapping[str, Any],
    edits: list[Edit],
    indexes: list[tuple[OperationKind, int, str]],
) -> EditsRejectedError:
    """project-index の 4xx・5xx を、変更ごとの理由つきの失敗にする。"""
    detail = str(
        body.get("detail") or body.get("title") or f"project-index が {status} を返却しました"
    )
    next_steps = [str(step) for step in body.get("nextSteps") or []]
    # 直コミットを許可していない種類: その種類の文書を変える変更ごとに理由を出す
    if status == HTTP_FORBIDDEN:
        kinds = {str(kind) for kind in body.get("kinds") or []}
        return EditsRejectedError(
            message=detail,
            status_code=HTTP_FORBIDDEN,
            errors=[
                EditError(key=edit.key, reason=f"{edit.doc_kind} は直コミットを許可していません")
                for edit in edits
                if edit.doc_kind in kinds
            ],
            next_steps=next_steps or [NEXT_STEP_WRITE_API_KINDS],
        )
    # 編集を始めたときのコミットが起点に使えない: 理由を detail に入れ、変更ごとの理由は持たない
    if status == HTTP_CONFLICT and body.get("title") == BASE_COMMIT_UNUSABLE:
        reason = body.get("reason")
        return EditsRejectedError(
            message=f"{detail}（{reason}）" if reason else detail,
            status_code=HTTP_CONFLICT,
            problem_title=BASE_COMMIT_UNUSABLE,
            next_steps=next_steps,
        )
    # 文書が無い・未コミットの変更・プッシュの拒否・検査に合格しない: 違反を変更へ戻す
    if status in (HTTP_NOT_FOUND, HTTP_CONFLICT, HTTP_UNPROCESSABLE):
        errors = [
            _violation(item, indexes, detail)
            for item in body.get("errors") or []
            if isinstance(item, Mapping)
        ]
        return EditsRejectedError(
            message=detail, status_code=status, errors=errors, next_steps=next_steps
        )
    # 書き込みの期限を過ぎた
    if status == HTTP_GATEWAY_TIMEOUT:
        return EditsRejectedError(
            message=f"project-index が書き込みの期限を過ぎました。{detail}",
            status_code=HTTP_GATEWAY_TIMEOUT,
            next_steps=[NEXT_STEP_RELOAD],
        )
    # リモート・生成の失敗と想定しない応答
    return EditsRejectedError(
        message=f"project-index が {status} を返却しました。{detail}",
        status_code=HTTP_BAD_GATEWAY,
        next_steps=next_steps,
    )


async def item_expected_versions(
    client: ProjectIndexClient,
    source_id: str,
    request: CommitRequest,
    mappings: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str] | str]:
    """`update` の変更ごとに、編集を始めたときの文書の修正した最上位のキーだけのバージョンを求める。

    修正したキーのどれかが編集を始めたときの文書に無い変更は、文書の全体のバージョンにする
    （空の辞書は project-index の照合で常に一致し、ほかの変更が同じ項目を加えても衝突にならないため）。
    """
    updates = [edit for edit in request.edits if edit.op == "update"]

    async def fetch(edit: Edit) -> dict[str, str] | None:
        """編集を始めたときの文書の `itemVersions`。文書が無ければ None。"""
        try:
            return await client.item_versions(
                source_id, str(edit.doc_path), ref=request.base_commit, document_id=edit.doc_id
            )
        except DocumentNotFoundError:
            return None

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(fetch(edit)) for edit in updates]
    except ExceptionGroup as group_error:
        first = group_error.exceptions[0]
        # 編集を始めたときのコミットがクローンに無い: 書き込みの API と同じく起点に使えないとして断る
        if isinstance(first, RefNotFoundError):
            raise EditsRejectedError(
                message=f"編集を始めたときのコミット {request.base_commit} がありません（not_found）",
                status_code=HTTP_CONFLICT,
                problem_title=BASE_COMMIT_UNUSABLE,
            ) from first
        raise first from None
    result: dict[str, dict[str, str] | str] = {}
    missing: list[EditError] = []
    for edit, task in zip(updates, tasks, strict=True):
        versions = task.result()
        # 編集を始めたときの文書が無い: project-index へ送信せずに 404 で断る
        if versions is None:
            missing.append(EditError(key=edit.key, reason="編集を始めたときの文書がありません"))
            continue
        metadata = mappings.get(edit.doc_kind)
        keys = {
            mapping.key
            for column in edit.values
            if (mapping := key_mapping(metadata, column)) is not None
        }
        # 編集を始めたときの文書に無い項目を加える: 文書の全体のバージョンで照合する
        if not keys <= versions.keys():
            result[edit.key] = str(edit.expected_version)
            continue
        result[edit.key] = {key: versions[key] for key in keys}
    if missing:
        raise EditsRejectedError(
            message="編集を始めたときの文書が見つかりません",
            status_code=HTTP_NOT_FOUND,
            errors=missing,
        )
    return result


def _pr_url(stdout: str) -> str | None:
    """標準出力の空でない最後の行が `https://` で始まるとき、その行を返却する。"""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if lines and lines[-1].startswith(PR_URL_PREFIX):
        return lines[-1]
    return None


def _conflict_reasons(
    item: Mapping[str, Any], index_keys: list[tuple[OperationKind, int, str]], edits: list[Edit]
) -> list[ConflictReason]:
    """`errors[]` の 1 件を変更の `key` と理由の組にする。"""
    violation = _violation(item, index_keys, "")
    # 文書のバージョンが合わない: `path` が文書の ID なので、その文書を変える変更ごとに 1 件にする
    if violation.key is None and violation.path is not None:
        keys = [edit.key for edit in edits if edit.doc_id == violation.path]
        if keys:
            return [ConflictReason(key=key, reason=violation.reason) for key in keys]
    return [ConflictReason(key=violation.key, reason=violation.reason)]


def to_conflict(
    conflict: Mapping[str, Any],
    index_keys: list[tuple[OperationKind, int, str]],
    edits: list[Edit],
) -> ConflictResult:
    """project-index の応答の `conflict` を、変更の `key` に戻した理由と PR の URL にする。"""
    reasons = [
        reason
        for item in conflict.get("errors") or []
        if isinstance(item, Mapping)
        for reason in _conflict_reasons(item, index_keys, edits)
    ]
    script = conflict.get("script")
    # スクリプトの指定が無い・差分確認: スクリプトの結果は無い
    result_script = (
        ConflictScript(
            exit_code=script.get("exitCode"),
            timed_out=bool(script.get("timedOut")),
            pr_url=_pr_url(str(script.get("stdout") or "")),
            stderr=str(script.get("stderr") or ""),
        )
        if isinstance(script, Mapping)
        else None
    )
    branch = conflict.get("branch")
    return ConflictResult(
        branch=None if branch is None else str(branch),
        base_commit=str(conflict.get("baseCommit") or ""),
        reasons=reasons,
        script=result_script,
    )


async def commit_edits(
    client: ProjectIndexClient, source_id: str, request: CommitRequest
) -> CommitResult:
    """変更を検証・変換して書き込みの API へ 1 回送信し、結果か変更ごとの理由を返却する。"""
    # 1. 種類ごとに修正できる列だけか
    _check_columns(request.edits)
    # 2. 列と文書のキーの対応（元のキーへ戻せる列かの確認に使用する）
    config = await client.source_config(source_id)
    mappings = {
        str(row.get("id")): {
            str(key): str(value) for key, value in (row.get("metadata") or {}).items()
        }
        for row in config.value.get("documents") or []
    }
    # 3. 編集を始めたときの項目ごとのバージョン
    expected_versions = await item_expected_versions(client, source_id, request, mappings)
    # 4. 書き込みと削除にして送信する
    writes, deletes, indexes = to_operations(request.edits, mappings, expected_versions)
    # project-index の書き込みの API は説明を必須にしているため、差分確認は固定の説明を送信する
    body: dict[str, Any] = {
        "writes": writes,
        "deletes": deletes,
        "message": DRY_RUN_MESSAGE if request.dry_run else request.message,
        "dryRun": request.dry_run,
        "baseCommit": request.base_commit,
    }
    try:
        status, response = await client.commit_documents(source_id, body)
    except ProjectIndexTimeoutError as error:
        logger.warning(
            "直コミットを打ち切った（%s・dryRun=%s・%d 件・待ちの上限）",
            source_id,
            request.dry_run,
            len(request.edits),
        )
        raise EditsRejectedError(
            message="project-index の応答を待つ上限を超えたため、コミットされたかが分かりません。",
            status_code=HTTP_GATEWAY_TIMEOUT,
            next_steps=[NEXT_STEP_RELOAD],
        ) from error
    commit = response.get("commit") if status == HTTP_OK else None
    raw_conflict = response.get("conflict") if status == HTTP_OK else None
    # 衝突したときは残したブランチ、コミットしたときはその SHA を記録する
    if isinstance(raw_conflict, Mapping):
        outcome = f"衝突・{raw_conflict.get('branch') or '-'}"
    else:
        outcome = (commit or {}).get("sha", "-") if isinstance(commit, Mapping) else "-"
    logger.info(
        "直コミットを送信した（%s・dryRun=%s・%d 件・%d・%s）",
        source_id,
        request.dry_run,
        len(request.edits),
        status,
        outcome,
    )
    if status != HTTP_OK:
        raise _rejected(status, response, request.edits, indexes)
    # 5. project-index の結果を変更の `key` に戻す
    results = [
        EditResult(
            key=_key_of(indexes, item.get("kind"), item.get("index")) or str(item.get("id", "")),
            status=item["status"],
            version=item.get("version"),
            diff=str(item.get("diff") or ""),
        )
        for item in response.get("results") or []
    ]
    return CommitResult(
        applied=bool(response.get("applied")),
        results=results,
        commit=CommitInfo(sha=str(commit["sha"]), branch=str(commit["branch"]))
        if isinstance(commit, Mapping)
        else None,
        conflict=to_conflict(raw_conflict, indexes, request.edits)
        if isinstance(raw_conflict, Mapping)
        else None,
    )
