"""画面の編集中の変更を文書の書き込みと削除に変えて、project-index の書き込みの API へ送信する。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from dev_docs.features.metadata.metadata import key_mapping
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.api_model import ApiModel
from dev_docs.shared.errors import DevDocsError, ProjectIndexTimeoutError

__all__ = [
    "EDITABLE_COLUMNS",
    "CommitRequest",
    "CommitResult",
    "Edit",
    "EditError",
    "EditsRejectedError",
    "commit_edits",
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
NEXT_STEP_RELOAD = "メタデータを再読み込みし、変更が反映されたかを確認してください。"

EditKind = Literal["terms", "aliases", "tags", "rules", "files"]
OperationKind = Literal["write", "delete"]


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
    values: dict[str, str | list[str]] = Field(default_factory=dict)


class CommitRequest(ApiModel):
    """直コミットの要求の本文。"""

    edits: list[Edit] = Field(min_length=1)
    message: str | None = None
    dry_run: bool = False

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


class CommitResult(ApiModel):
    """直コミットの 200 の応答。"""

    applied: bool
    results: list[EditResult]
    commit: CommitInfo | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EditError:
    """変更ごとの理由（`key` が `None` は本文全体）。"""

    key: str | None
    reason: str
    path: str | None = None
    current: str | None = None


@dataclass(kw_only=True)
class EditsRejectedError(DevDocsError):
    """状態コードと変更ごとの理由つきの失敗。"""

    status: ClassVar[int] = 400
    status_code: int = HTTP_BAD_REQUEST
    errors: list[EditError] = field(default_factory=list)

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
                        ("current", item.current),
                    )
                    if value is not None
                }
                for item in self.errors
            ]
        }


def _mapped_values(
    edit: Edit,
    metadata: Mapping[str, str] | None,
    current: Mapping[str, object],
) -> dict[str, Any]:
    """変更の値を、文書の実際のキーと値に戻す。"""
    result: dict[str, Any] = {}
    for column, value in edit.values.items():
        mapping = key_mapping(metadata, column)
        # 入れ子のパス・絞り込み: 戻せない
        if mapping is None:
            raise EditsRejectedError(
                message="元のキーへ戻せない列を修正しています",
                status_code=HTTP_BAD_REQUEST,
                errors=[EditError(key=edit.key, path=column, reason="この列は修正できません")],
            )
        # 最上位のキー: 値をそのまま
        if mapping.item is None:
            result[mapping.key] = value
            continue
        # オブジェクトの配列の項目: 残る要素はオブジェクトのまま並び順を保ち、追加した値を末尾に追加する
        sent = value if isinstance(value, list) else [value]
        items = current.get(mapping.key)
        existing = [
            item for item in (items if isinstance(items, list) else []) if isinstance(item, Mapping)
        ]
        kept = [dict(item) for item in existing if item.get(mapping.item) in sent]
        names = {item.get(mapping.item) for item in kept}
        result[mapping.key] = kept + [{mapping.item: name} for name in sent if name not in names]
    return result


def to_operations(
    edits: list[Edit],
    mappings: Mapping[str, Mapping[str, str]],
    current_values: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[OperationKind, int, str]]]:
    """編集中の変更を、文書の実際のキーへ戻した `writes`・`deletes` と、添字と変更の `key` の対応にする。"""
    writes: list[dict[str, Any]] = []
    deletes: list[dict[str, Any]] = []
    indexes: list[tuple[OperationKind, int, str]] = []
    for edit in edits:
        if edit.op == "delete":
            indexes.append(("delete", len(deletes), edit.key))
            deletes.append({"id": edit.doc_id, "expectedVersion": edit.expected_version})
            continue
        values = _mapped_values(
            edit, mappings.get(edit.doc_kind), current_values.get(edit.doc_id) or {}
        )
        indexes.append(("write", len(writes), edit.key))
        if edit.op == "update":
            writes.append(
                {
                    "op": "update",
                    "id": edit.doc_id,
                    "expected_version": edit.expected_version,
                    "set": values,
                }
            )
        else:
            writes.append(
                {"op": "create", "id": edit.doc_id, "kind": edit.doc_kind, "data": values}
            )
    return writes, deletes, indexes


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


def _needs_current(edit: Edit, metadata: Mapping[str, str] | None) -> bool:
    """`{キー}[].{項目}` の列を変える `update` か。"""
    if edit.op != "update":
        return False
    for column in edit.values:
        mapping = key_mapping(metadata, column)
        if mapping is not None and mapping.item is not None:
            return True
    return False


async def _current_values(
    client: ProjectIndexClient,
    source_id: str,
    edits: list[Edit],
    mappings: Mapping[str, Mapping[str, str]],
) -> dict[str, Mapping[str, object]]:
    """配列の項目を変える文書の今の値を取得し、バージョンが違えば 409 にする。"""
    targets = [edit for edit in edits if _needs_current(edit, mappings.get(edit.doc_kind))]
    if not targets:
        return {}
    documents = {
        (document.kind, document.id): document
        for document in (await client.list_documents(source_id, values=True)).documents
    }
    result: dict[str, Mapping[str, object]] = {}
    conflicts: list[EditError] = []
    for edit in targets:
        document = documents.get((edit.doc_kind, edit.doc_id))
        if document is None:
            raise EditsRejectedError(
                message="修正する文書がありません",
                status_code=HTTP_NOT_FOUND,
                errors=[EditError(key=edit.key, reason="文書がありません")],
            )
        if document.version != edit.expected_version:
            conflicts.append(
                EditError(
                    key=edit.key,
                    reason="参照した後に文書が変わっています",
                    current=document.version,
                )
            )
        result[edit.doc_id] = document.data
    if conflicts:
        raise EditsRejectedError(
            message="参照した後に変わった文書があります",
            status_code=HTTP_CONFLICT,
            errors=conflicts,
            next_steps=[NEXT_STEP_RELOAD],
        )
    return result


def _key_of(
    indexes: list[tuple[OperationKind, int, str]], kind: object, index: object
) -> str | None:
    """project-index の `writes`・`deletes` の別と添字を、変更の `key` に戻す。"""
    target: OperationKind = "delete" if kind == "deletes" else "write"
    return next((key for op, position, key in indexes if op == target and position == index), None)


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
    # 文書が無い・バージョンが合わない・検査に合格しない: 違反を変更へ戻す
    if status in (HTTP_NOT_FOUND, HTTP_CONFLICT, HTTP_UNPROCESSABLE):
        errors = [
            EditError(
                key=_key_of(indexes, item.get("kind"), item.get("index")),
                path=None if item.get("path") is None else str(item.get("path")),
                reason=str(item.get("reason") or detail),
                current=None if item.get("current") is None else str(item.get("current")),
            )
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


async def commit_edits(
    client: ProjectIndexClient, source_id: str, request: CommitRequest
) -> CommitResult:
    """変更を検証・変換して書き込みの API へ 1 回送信し、結果か変更ごとの理由を返却する。"""
    # 1. 種類ごとに修正できる列だけか
    _check_columns(request.edits)
    # 2. 列と文書のキーの対応と、配列の項目を変える文書の今の値
    config = await client.source_config(source_id)
    mappings = {
        str(row.get("id")): {
            str(key): str(value) for key, value in (row.get("metadata") or {}).items()
        }
        for row in config.value.get("documents") or []
    }
    current = await _current_values(client, source_id, request.edits, mappings)
    # 3. 書き込みと削除にして送信する
    writes, deletes, indexes = to_operations(request.edits, mappings, current)
    body: dict[str, Any] = {"writes": writes, "deletes": deletes, "dryRun": request.dry_run}
    if request.message:
        body["message"] = request.message
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
    logger.info(
        "直コミットを送信した（%s・dryRun=%s・%d 件・%d・%s）",
        source_id,
        request.dry_run,
        len(request.edits),
        status,
        (commit or {}).get("sha", "-") if isinstance(commit, Mapping) else "-",
    )
    if status != HTTP_OK:
        raise _rejected(status, response, request.edits, indexes)
    # 4. project-index の結果を変更の `key` に戻す
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
    )
