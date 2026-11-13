"""project-index の読み取り API と端末の設定の API の呼び出し。"""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from dev_docs.integrations.project_index.types import (
    METADATA_KEYS,
    AddSourceResult,
    CommitSummary,
    DecisionIndex,
    DocumentDetail,
    DocumentList,
    DocumentRow,
    IndexedDocument,
    IndexFailure,
    NamedRef,
    RefList,
    SearchHit,
    SearchHits,
    SettingsSourcesView,
    SourceState,
    SourceView,
    parse_datetime,
    parse_document,
)
from dev_docs.shared.errors import (
    DocumentNotFoundError,
    InvalidArgumentError,
    ProjectIndexRejectedError,
    ProjectIndexResponseError,
    ProjectIndexUnreachableError,
    RefNotFoundError,
    SourceNotServedError,
    UnknownSourceError,
    Violation,
)

PROJECT_INDEX_DEFAULT = "http://127.0.0.1:8786"
PROJECT_INDEX_TIMEOUT_SEC = 45
SUMMARY_CHARS = 200
ROW_KEYS = ("id", "config", "enabled", "scope")
REFUSED_REASON = "接続を拒否されました（Connection refused）"
HTTP_CONFLICT = 409
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422
SUCCESS_MIN = 200
SUCCESS_MAX = 299


def _seg(value: str) -> str:
    """パスの要素を URL エンコードする（`/` も含めて）。"""
    return quote(value, safe="")


def _violations(errors: Any) -> list[Violation]:
    """problem+json の `errors[]` の `{path, reason}` を `Violation` にする。"""
    return [
        Violation(path=str(item.get("path", "")), rule=str(item.get("reason", "")))
        for item in errors or []
        if isinstance(item, Mapping)
    ]


def _failure(value: Any) -> IndexFailure | None:
    """変換か読み込みの失敗の JSON を解析する。"""
    if not isinstance(value, Mapping):
        return None
    return IndexFailure(
        reason=value["reason"],
        kind=str(value.get("kind", "")),
        detail=str(value.get("detail", "")),
        script=value.get("script"),
        file=value.get("file"),
        line=value.get("line"),
        column=value.get("column"),
    )


def _row(value: Mapping[str, Any]) -> dict[str, Any]:
    """端末の設定の取得の 1 件から、端末の設定の行のキーの辞書を作る。"""
    row = {key: value[key] for key in ROW_KEYS if key in value}
    if "outsideRead" in value:
        row["outside_read"] = value["outsideRead"]
    return row


def _state(value: Mapping[str, Any]) -> SourceState:
    """配信元の状態の JSON を解析する。"""
    version = value.get("configVersion")
    return SourceState(
        id=value.get("id"),
        status=value["status"],
        errors=_violations(value.get("errors")),
        config=list(value.get("config") or []),
        config_version=(
            (str(version["config"]), str(version["server"]))
            if isinstance(version, Mapping)
            else None
        ),
    )


class ProjectIndexClient:
    """project-index の API を `httpx.AsyncClient` で呼び、応答を型にする。"""

    def __init__(
        self,
        address: str,
        *,
        timeout: float = PROJECT_INDEX_TIMEOUT_SEC,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.address = address.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.address, timeout=timeout, transport=transport
        )

    async def aclose(self) -> None:
        """HTTP のクライアントを閉じる。"""
        await self._client.aclose()

    def _unreachable(self, reason: str) -> ProjectIndexUnreachableError:
        return ProjectIndexUnreachableError(address=self.address, reason=reason)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        body: Any = None,
    ) -> httpx.Response:
        """project-index へ 1 回要求し、つながらない・打ち切った・断られたことを例外に変える。"""
        query = {key: value for key, value in (params or {}).items() if value is not None}
        timed_out = f"{self.timeout:g} 秒以内に応答がありませんでした"
        try:
            async with asyncio.timeout(self.timeout):
                response = await self._client.request(method, path, params=query, json=body)
                await response.aread()
        except httpx.ConnectError as error:
            raise self._unreachable(REFUSED_REASON) from error
        except (TimeoutError, httpx.TimeoutException) as error:
            raise self._unreachable(timed_out) from error
        except httpx.TransportError as error:
            raise self._unreachable(str(error)) from error
        status = response.status_code
        if SUCCESS_MIN <= status <= SUCCESS_MAX or status == HTTP_CONFLICT:
            return response
        problem: dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                problem = parsed
        except ValueError:
            problem = {}
        detail = str(problem.get("detail", ""))
        if status == HTTP_NOT_FOUND:
            missing = problem.get("missing")
            value = str(problem.get("value", ""))
            if missing == "source":
                raise UnknownSourceError(
                    message=detail or f"配信元がありません: {value}", source_id=value
                )
            if missing == "not_served":
                raise SourceNotServedError(
                    message=detail or f"{value} は配信していません",
                    violations=_violations(problem.get("errors")),
                    disabled=bool(problem.get("disabled", False)),
                )
            if missing == "ref":
                raise RefNotFoundError(
                    message=detail or f"ref を解決できません: {value}",
                    argument=str(problem.get("argument") or "ref"),
                    value=value,
                )
            raise DocumentNotFoundError(
                message=detail or f"文書がありません: {value}", missing=[value]
            )
        if status == HTTP_BAD_REQUEST:
            raise InvalidArgumentError(
                message=detail, violations=_violations(problem.get("errors"))
            )
        if status == HTTP_UNPROCESSABLE:
            raise ProjectIndexRejectedError(
                message=detail or "project-index が要求を受け付けませんでした",
                violations=_violations(problem.get("errors")),
            )
        summary = response.text[:SUMMARY_CHARS]
        raise ProjectIndexResponseError(
            message=f"project-index が {status} を返却しました: {summary}",
            status_code=status,
            summary=summary,
        )

    async def list_sources(self) -> list[SourceState]:
        """配信元の一覧と配信元ごとの状態を返却する。"""
        response = await self.request("GET", "/sources")
        return [_state(item) for item in response.json().get("sources", [])]

    async def source_view(self, source: str) -> SourceView:
        """配信元の設定のうち画面が使用するキーと、Git の配信元か・既定のリビジョンを返却する。"""
        config_response, refs_response = await asyncio.gather(
            self.request("GET", f"/sources/{_seg(source)}/config", params={"schemas": "true"}),
            self.request("GET", f"/sources/{_seg(source)}/refs", params={"commits": 0}),
        )
        value = config_response.json()
        refs = refs_response.json()
        git = bool(refs.get("git", False))
        schemas = value.get("schemas") or {}
        decisions = value.get("decisions") or {}
        github = value.get("github") or {}
        diff = value.get("diff") or {}
        return SourceView(
            id=source,
            git=git,
            default_ref=str(refs.get("defaultRef")) if git else None,
            nav=value.get("nav"),
            documents=[
                DocumentRow(
                    id=str(row["id"]),
                    paths=list(row.get("paths") or []),
                    schema=dict(schemas.get(str(row["id"])) or {}),
                    title=row.get("title"),
                    records=row.get("records"),
                    search=bool(row.get("search", True)),
                    converter=row.get("converter"),
                    alias_type=row.get("alias_type"),
                    metadata={str(k): str(v) for k, v in (row.get("metadata") or {}).items()},
                )
                for row in value.get("documents") or []
            ],
            decision_folders=list(decisions.get("folders") or []),
            diff_ignore_keys=list(diff.get("ignore_keys") or ["updated"]),
            github_repository=github.get("repository"),
            github_issue_labels=list(github.get("issueLabels") or []),
        )

    async def list_documents(
        self,
        source: str,
        *,
        ref: str | None = None,
        record_kinds: Collection[str] = (),
        values: bool = True,
    ) -> DocumentList:
        """リビジョンの全ての文書を返却する。"""
        response = await self.request(
            "GET",
            f"/sources/{_seg(source)}/docs",
            params={"ref": ref, "values": "true" if values else None},
        )
        value = response.json()
        positions: dict[str, int] = {}
        documents: list[IndexedDocument] = []
        for item in value.get("documents") or []:
            record_index: int | None = None
            if item.get("kind") in record_kinds:
                path = str(item.get("path", ""))
                record_index = positions.get(path, 0)
                positions[path] = record_index + 1
            documents.append(parse_document(source, item, record_index=record_index))
        return DocumentList(ref=value.get("ref") or None, documents=documents)

    async def document(
        self,
        source: str,
        path: str,
        *,
        ref: str | None = None,
        document_id: str | None = None,
    ) -> DocumentDetail:
        """1 件の文書の値・本文と、`converters[]` の Markdown か失敗を返却する。"""
        encoded = "/".join(_seg(part) for part in path.split("/"))
        response = await self.request(
            "GET",
            f"/sources/{_seg(source)}/docs/{encoded}",
            params={"ref": ref, "id": document_id},
        )
        value = response.json()
        metadata = value.get("metadata") or {}
        document: IndexedDocument | None = None
        if value.get("value") is not None:
            document = IndexedDocument(
                id=str(metadata.get("id", "")),
                kind=str(metadata.get("kind", "")),
                source_id=source,
                path=str(value.get("path", path)),
                data=dict(value["value"]),
                metadata={key: metadata.get(key) for key in METADATA_KEYS},
                version="",
                body=str(value.get("body") or ""),
                body_path=value.get("bodyPath"),
                updated=parse_datetime(value.get("updatedAt")),
            )
        return DocumentDetail(
            document=document,
            markdown=value.get("markdown"),
            failure=_failure(value.get("conversionError")),
        )

    async def decisions(self, source: str) -> DecisionIndex:
        """検討事項の ID ごとの当たるフォルダの数を返却する。"""
        response = await self.request("GET", f"/sources/{_seg(source)}/decisions")
        return DecisionIndex(
            counts={
                str(item["id"]): int(item.get("folders", 0))
                for item in response.json().get("decisions") or []
            }
        )

    async def decision(self, source: str, decision_id: str) -> str:
        """ちょうど 1 つのフォルダにある検討事項の文書の本文を返却する。"""
        response = await self.request(
            "GET", f"/sources/{_seg(source)}/decisions/{_seg(decision_id)}"
        )
        return str(response.json().get("body", ""))

    async def search(
        self, source: str, q: str, *, ref: str | None = None, limit: int
    ) -> SearchHits:
        """単語を含む文書と一致した箇所を返却する。"""
        response = await self.request(
            "GET",
            f"/sources/{_seg(source)}/search",
            params={"q": q, "ref": ref, "limit": limit},
        )
        value = response.json()
        return SearchHits(
            total_count=int(value.get("totalCount", 0)),
            items=[
                SearchHit(
                    id=str(item.get("id", "")),
                    path=str(item.get("filePath", "")),
                    name=str(item.get("name", "")),
                    snippets=list(item.get("snippets") or []),
                )
                for item in value.get("items") or []
            ],
        )

    async def refs(self, source: str, *, commits: int) -> RefList:
        """配信元のブランチ・タグ・最近の commit を返却する。"""
        response = await self.request(
            "GET", f"/sources/{_seg(source)}/refs", params={"commits": commits}
        )
        value = response.json()
        return RefList(
            git=bool(value.get("git", False)),
            default_ref=str(value.get("defaultRef", "")),
            branches=[
                NamedRef(name=b["name"], commit=b["commit"]) for b in value.get("branches") or []
            ],
            tags=[NamedRef(name=t["name"], commit=t["commit"]) for t in value.get("tags") or []],
            commits=[
                CommitSummary(
                    commit=c["commit"],
                    date=datetime.fromisoformat(c["date"]),
                    subject=str(c.get("subject", "")),
                )
                for c in value.get("commits") or []
            ],
        )

    def _settings(self, value: Mapping[str, Any]) -> SettingsSourcesView:
        sources = list(value.get("sources") or [])
        return SettingsSourcesView(
            settings_path=str(value.get("settingsPath", "")),
            rows=[_row(item) for item in sources],
            states=[_state(item) for item in sources],
        )

    async def settings_sources(self) -> SettingsSourcesView:
        """project-index の端末の設定の `sources[]` の行と状態を返却する。"""
        response = await self.request("GET", "/settings/sources")
        return self._settings(response.json())

    async def put_settings_sources(self, rows: list[dict[str, Any]]) -> SettingsSourcesView:
        """`sources[]` の全行の保存と読み直しを依頼し、保存した後の行と状態を返却する。"""
        await self.request("PUT", "/settings/sources", body={"sources": rows})
        return await self.settings_sources()

    async def add_settings_source(self, row: Mapping[str, Any]) -> AddSourceResult:
        """配信元の行を 1 行追加する。同じ id の行があれば追加しない。"""
        response = await self.request("POST", "/settings/sources", body={"source": dict(row)})
        value = response.json()
        if value.get("result") == "exists":
            return AddSourceResult(added=False, same=bool(value.get("same", False)))
        return AddSourceResult(added=True)
