from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import pytest

from dev_docs.features.metadata.commits import (
    CommitRequest,
    Edit,
    EditsRejectedError,
    commit_edits,
    to_operations,
)
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexTimeoutError

from ...conftest import FakeIndex, config_json, doc_json

COMMITS_PATH = ("POST", "/sources/sample/commits")
CONFIG_ROWS = [
    {"id": "terms", "paths": ["glossary.yaml"], "records": "terms", "alias_type": "term"},
    {"id": "note", "paths": ["notes/*.yaml"], "alias_type": "doc"},
]


def _edits() -> list[Edit]:
    """タグの `update`・用語の `add`・用語の `delete` の 3 件。"""
    return [
        Edit(
            key="tags:n1:update",
            kind="tags",
            op="update",
            doc_id="n1",
            doc_kind="note",
            expected_version="c3d4e5",
            values={"tags": ["topic:a", "topic:b"]},
        ),
        Edit(
            key="terms:kind:add",
            kind="terms",
            op="add",
            doc_id="kind",
            doc_kind="terms",
            values={"name": "種類", "description": "文書の行の ID"},
        ),
        Edit(
            key="terms:old-name:delete",
            kind="terms",
            op="delete",
            doc_id="old-name",
            doc_kind="terms",
            expected_version="b2c3d4",
        ),
    ]


def _prepare(fake_index: FakeIndex, status: int, body: dict[str, Any]) -> None:
    """配信元の設定と、書き込みの API の応答を偽物に配置する。"""
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[COMMITS_PATH] = (status, body)


def test_to_operations() -> None:
    """update・add・delete を変換する（正常系）。"""
    # 準備
    edits = _edits()
    # 実行
    writes, deletes, indexes = to_operations(edits, {}, {})
    # 検証
    assert writes == [
        {
            "op": "update",
            "id": "n1",
            "expected_version": "c3d4e5",
            "set": {"tags": ["topic:a", "topic:b"]},
        },
        {
            "op": "create",
            "id": "kind",
            "kind": "terms",
            "data": {"name": "種類", "description": "文書の行の ID"},
        },
    ]
    assert deletes == [{"id": "old-name", "expectedVersion": "b2c3d4"}]
    assert indexes == [
        ("write", 0, "tags:n1:update"),
        ("write", 1, "terms:kind:add"),
        ("delete", 0, "terms:old-name:delete"),
    ]


def test_to_operations_when_mapped_tags() -> None:
    """オブジェクトの配列のほかの項目を保つ（正常系）。"""
    # 準備
    edit = Edit(
        key="tags:n1:update",
        kind="tags",
        op="update",
        doc_id="n1",
        doc_kind="note",
        expected_version="c3d4e5",
        values={"tags": ["topic:a", "topic:b"]},
    )
    mappings = {"note": {"tags": "tags[].name"}}
    current = {"n1": {"tags": [{"name": "topic:a", "main": True}, {"name": "topic:c"}]}}
    # 実行
    writes, _, _ = to_operations([edit], mappings, current)
    # 検証
    assert writes[0]["set"] == {"tags": [{"name": "topic:a", "main": True}, {"name": "topic:b"}]}


def test_to_operations_when_unmappable() -> None:
    """戻せない列（異常系）。"""
    # 準備
    edit = Edit(
        key="aliases:s1:update",
        kind="aliases",
        op="update",
        doc_id="s1",
        doc_kind="skill",
        expected_version="a1",
        values={"name": "スキル"},
    )
    mappings = {"skill": {"name": "skill.path"}}
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        to_operations([edit], mappings, {})
    # 検証
    assert caught.value.status_code == 400
    assert [error.key for error in caught.value.errors] == ["aliases:s1:update"]


def test_to_operations_when_mapped_name() -> None:
    """対応づけた最上位のキーへ戻す（正常系）。"""
    # 準備
    edit = Edit(
        key="aliases:s1:update",
        kind="aliases",
        op="update",
        doc_id="s1",
        doc_kind="skill",
        expected_version="a1",
        values={"name": "スキル"},
    )
    mappings = {"skill": {"name": "title"}}
    # 実行
    writes, _, _ = to_operations([edit], mappings, {})
    # 検証
    assert writes[0]["set"] == {"title": "スキル"}


def test_commit_edits(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """変更ごとの結果に戻す（正常系）。"""
    # 準備
    _prepare(
        fake_index,
        200,
        {
            "applied": True,
            "results": [
                {
                    "kind": "writes",
                    "index": 0,
                    "id": "n1",
                    "status": "updated",
                    "version": "v2",
                    "diff": "d0",
                },
                {
                    "kind": "writes",
                    "index": 1,
                    "id": "kind",
                    "status": "created",
                    "version": "v3",
                    "diff": "d1",
                },
                {
                    "kind": "deletes",
                    "index": 0,
                    "id": "old-name",
                    "status": "deleted",
                    "version": None,
                    "diff": "d2",
                },
            ],
            "commit": {"sha": "0a1b2c3", "branch": "develop", "retried": False},
        },
    )
    request = CommitRequest(edits=_edits(), message="用語とタグを追加する")
    caplog.set_level(logging.INFO, logger="dev_docs.features.metadata.commits")
    # 実行
    result = asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    assert result.applied is True
    assert [(item.key, item.status) for item in result.results] == [
        ("tags:n1:update", "updated"),
        ("terms:kind:add", "created"),
        ("terms:old-name:delete", "deleted"),
    ]
    assert result.commit is not None
    assert result.commit.sha == "0a1b2c3"
    assert len(caplog.records) == 1


def test_commit_edits_when_validation_failed(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """422 の違反を変更へ戻す（異常系）。"""
    # 準備
    _prepare(
        fake_index,
        422,
        {
            "title": "ValidationFailedError",
            "status": 422,
            "detail": "検査に合格しませんでした",
            "errors": [
                {"kind": "writes", "index": 1, "path": "name", "reason": "必須のキーが無い"}
            ],
        },
    )
    request = CommitRequest(edits=_edits(), message="用語とタグを追加する")
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    assert caught.value.status_code == 422
    assert caught.value.errors[0].key == "terms:kind:add"
    assert caught.value.errors[0].reason == "必須のキーが無い"


def test_commit_edits_when_not_permitted(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """403 の種類を変更へ戻す（異常系）。"""
    # 準備
    _prepare(
        fake_index,
        403,
        {
            "title": "DirectCommitNotPermittedError",
            "status": 403,
            "detail": "直コミットを許可していない種類があります",
            "kinds": ["note"],
            "nextSteps": ["sources[].direct_commit.write_api_kinds に種類を追加してください"],
        },
    )
    request = CommitRequest(edits=_edits(), message="用語とタグを追加する")
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    assert caught.value.status_code == 403
    assert [error.key for error in caught.value.errors] == ["tags:n1:update"]
    assert any("write_api_kinds" in step for step in caught.value.next_steps)


def test_commit_edits_when_timed_out(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """待ちの上限（異常系）。"""

    # 準備
    async def timed_out(*_: Any, **__: Any) -> Any:
        raise ProjectIndexTimeoutError(address="http://127.0.0.1:8786", reason="72 秒")

    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    client = make_client()
    monkeypatch.setattr(client, "commit_documents", timed_out)
    request = CommitRequest(edits=_edits(), message="用語とタグを追加する")
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(client, "sample", request))
    # 検証
    assert caught.value.status_code == 504
    assert "コミットされたか" in caught.value.message


def test_commit_edits_when_dry_run(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """差分確認でも説明を送信する（正常系）。"""
    # 準備
    _prepare(fake_index, 200, {"applied": False, "results": [], "commit": None})
    request = CommitRequest(edits=_edits(), dry_run=True)
    # 実行
    asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    sent = next(item for item in fake_index.requests if item.method == "POST")
    body = json.loads(sent.content)
    assert body["message"] == "差分確認"
    assert body["dryRun"] is True


def test_commit_edits_when_mapped_tags(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """対象の文書だけを取得する（正常系）。"""
    # 準備
    note_row = {
        "id": "note",
        "paths": ["notes/*.yaml"],
        "alias_type": "doc",
        "metadata": {"tags": "tags[].name"},
    }
    fake_index.configs["sample"] = config_json(documents=[note_row])
    fake_index.docs["sample"] = {
        None: [
            doc_json(
                "n1",
                "notes/n1.yaml",
                kind="note",
                data={"id": "n1", "tags": [{"name": "topic:a", "main": True}]},
                version="c3d4e5",
            )
        ]
    }
    fake_index.responses[COMMITS_PATH] = (
        200,
        {"applied": False, "results": [], "commit": None},
    )
    edit = Edit(
        key="tags:n1:update",
        kind="tags",
        op="update",
        doc_id="n1",
        doc_kind="note",
        doc_path="notes/n1.yaml",
        expected_version="c3d4e5",
        values={"tags": ["topic:a", "topic:b"]},
    )
    # 実行
    asyncio.run(commit_edits(make_client(), "sample", CommitRequest(edits=[edit], dry_run=True)))
    # 検証
    paths = [
        (item.method, item.url.path, item.url.params.get("id")) for item in fake_index.requests
    ]
    assert ("GET", "/sources/sample/docs/notes/n1.yaml", "n1") in paths
    assert ("GET", "/sources/sample/docs", None) not in paths
    sent = json.loads(next(item for item in fake_index.requests if item.method == "POST").content)
    assert sent["writes"][0]["set"] == {
        "tags": [{"name": "topic:a", "main": True}, {"name": "topic:b"}]
    }
