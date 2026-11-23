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
    item_expected_versions,
    to_conflict,
    to_operations,
)
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexTimeoutError

from ...conftest import FakeIndex, config_json

COMMITS_PATH = ("POST", "/sources/sample/commits")
N1_PATH = ("GET", "/sources/sample/docs/notes/n1.yaml")
BASE_COMMIT = "0a1b2c3"
N1_VERSIONS = {"id": "i1", "name": "m1", "tags": "t1"}
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
            doc_path="notes/n1.yaml",
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
    fake_index.responses[N1_PATH] = (200, {"path": "notes/n1.yaml", "itemVersions": N1_VERSIONS})
    fake_index.responses[COMMITS_PATH] = (status, body)


def _request(**overrides: Any) -> CommitRequest:
    """3 件の変更と編集を始めたときのコミットを持つ要求を作る。"""
    values: dict[str, Any] = {
        "edits": _edits(),
        "message": "用語とタグを追加する",
        "base_commit": BASE_COMMIT,
    }
    return CommitRequest(**{**values, **overrides})


def test_to_operations() -> None:
    """update・add・delete を変換する（正常系）。"""
    # 準備
    edits = _edits()
    # 実行
    writes, deletes, indexes = to_operations(edits, {}, {"tags:n1:update": {"tags": "t1"}})
    # 検証
    assert writes == [
        {
            "op": "update",
            "id": "n1",
            "expected_version": {"tags": "t1"},
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
    """対応づけた配列の項目の列は名前の配列のまま入れる（正常系）。"""
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
    # 実行
    writes, _, _ = to_operations([edit], mappings, {})
    # 検証
    assert writes[0]["set"] == {"tags": ["topic:a", "topic:b"]}


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
    """対応づけた最上位のキーの列も共通のキーのまま入れる（正常系）。"""
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
    assert writes[0]["set"] == {"name": "スキル"}


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
                    "kind": "write",
                    "index": 0,
                    "id": "n1",
                    "status": "updated",
                    "version": "v2",
                    "diff": "d0",
                },
                {
                    "kind": "write",
                    "index": 1,
                    "id": "kind",
                    "status": "created",
                    "version": "v3",
                    "diff": "d1",
                },
                {
                    "kind": "delete",
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
    request = _request()
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
            "errors": [{"path": "writes[1].name", "reason": "必須のキーが無い"}],
        },
    )
    request = _request()
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    assert caught.value.status_code == 422
    assert caught.value.errors[0].key == "terms:kind:add"
    assert caught.value.errors[0].path == "name"
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
    request = _request()
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
    fake_index.responses[N1_PATH] = (200, {"path": "notes/n1.yaml", "itemVersions": N1_VERSIONS})
    client = make_client()
    monkeypatch.setattr(client, "commit_documents", timed_out)
    request = _request()
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
    request = _request(message=None, dry_run=True)
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
    """対応づけた配列の項目の列でも文書を取得しない（正常系）。"""
    # 準備
    note_row = {
        "id": "note",
        "paths": ["notes/*.yaml"],
        "alias_type": "doc",
        "metadata": {"tags": "tags[].name"},
    }
    fake_index.configs["sample"] = config_json(documents=[note_row])
    fake_index.responses[N1_PATH] = (200, {"path": "notes/n1.yaml", "itemVersions": N1_VERSIONS})
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
        expected_version="c3d4e5",
        doc_path="notes/n1.yaml",
        values={"tags": ["topic:a", "topic:b"]},
    )
    request = CommitRequest(edits=[edit], dry_run=True, base_commit=BASE_COMMIT)
    # 実行
    asyncio.run(commit_edits(make_client(), "sample", request))
    # 検証
    gets = [
        (item.url.path, item.url.params.get("ref"), item.url.params.get("id"))
        for item in fake_index.requests
        if item.method == "GET" and item.url.path.startswith("/sources/sample/docs")
    ]
    assert gets == [("/sources/sample/docs/notes/n1.yaml", BASE_COMMIT, "n1")]
    sent = json.loads(next(item for item in fake_index.requests if item.method == "POST").content)
    assert sent["writes"][0]["set"] == {"tags": ["topic:a", "topic:b"]}
    assert sent["writes"][0]["expected_version"] == {"tags": "t1"}


def test_commit_edits_when_base_commit_unusable(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """編集を始めたときのコミットが使用できない（異常系）。"""
    # 準備
    _prepare(
        fake_index,
        409,
        {
            "title": "BaseCommitUnusableError",
            "status": 409,
            "detail": "編集を始めたときのコミットが既定のブランチの祖先ではありません",
            "reason": "not_ancestor",
        },
    )
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(make_client(), "sample", _request()))
    # 検証
    assert caught.value.status_code == 409
    assert caught.value.name == "BaseCommitUnusableError"
    assert "not_ancestor" in caught.value.message
    assert caught.value.errors == []


def test_commit_edits_when_conflict(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """衝突してブランチに残した（正常系）。"""
    # 準備
    _prepare(
        fake_index,
        200,
        {
            "applied": False,
            "results": [],
            "commit": None,
            "conflict": {
                "branch": "project-index/conflict/20261123-103000-0a1b2c3",
                "commit": "1b2c3d4",
                "baseCommit": BASE_COMMIT,
                "errors": [{"path": "writes[0].tags", "reason": "tags が変わっています"}],
                "script": {
                    "exitCode": 0,
                    "timedOut": False,
                    "stdout": "pushed\nhttps://github.com/o/r/pull/9\n",
                    "stderr": "",
                },
            },
        },
    )
    # 実行
    result = asyncio.run(commit_edits(make_client(), "sample", _request()))
    # 検証
    assert result.conflict is not None
    assert result.conflict.branch == "project-index/conflict/20261123-103000-0a1b2c3"
    assert result.conflict.reasons[0].key == "tags:n1:update"
    assert result.conflict.script is not None
    assert result.conflict.script.pr_url == "https://github.com/o/r/pull/9"
    sent = json.loads(next(item for item in fake_index.requests if item.method == "POST").content)
    assert sent["baseCommit"] == BASE_COMMIT
    assert sent["writes"][0]["expected_version"] == {"tags": "t1"}


def test_item_expected_versions(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """修正した最上位のキーだけにする（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[N1_PATH] = (
        200,
        {"path": "notes/n1.yaml", "itemVersions": {"name": "m1", "description": "d1", "tags": "t1"}},
    )
    mappings = {"note": {"tags": "tags[].name"}}
    # 実行
    versions = asyncio.run(
        item_expected_versions(make_client(), "sample", _request(), mappings)
    )
    # 検証
    assert versions == {"tags:n1:update": {"tags": "t1"}}
    detail = next(item for item in fake_index.requests if item.url.path.endswith("n1.yaml"))
    assert (detail.url.params.get("ref"), detail.url.params.get("id")) == (BASE_COMMIT, "n1")


def test_item_expected_versions_when_not_found(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """編集を始めたときの文書が無い（異常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[N1_PATH] = (200, {"path": "notes/n1.yaml", "itemVersions": N1_VERSIONS})
    second = Edit(
        key="tags:n2:update",
        kind="tags",
        op="update",
        doc_id="n2",
        doc_kind="note",
        expected_version="d4",
        doc_path="notes/n2.yaml",
        values={"tags": ["topic:c"]},
    )
    request = _request(edits=[_edits()[0], second])
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(item_expected_versions(make_client(), "sample", request, {}))
    # 検証
    assert caught.value.status_code == 404
    assert [error.key for error in caught.value.errors] == ["tags:n2:update"]


def test_to_conflict() -> None:
    """理由を変更へ戻し、PR の URL を取り出す（正常系）。"""
    # 準備
    conflict = {
        "branch": "project-index/conflict/20261123-103000-0a1b2c3",
        "commit": "1b2c3d4",
        "baseCommit": BASE_COMMIT,
        "errors": [
            {"path": "writes[1].name", "reason": "name が変わっています"},
            {"path": "", "reason": "既定のブランチが進んでいます"},
        ],
        "script": {
            "exitCode": 0,
            "timedOut": False,
            "stdout": "pushed\nhttps://github.com/o/r/pull/9\n",
            "stderr": "",
        },
    }
    indexes = [("write", 0, "tags:n1:update"), ("write", 1, "terms:kind:add")]
    # 実行
    result = to_conflict(conflict, indexes)
    # 検証
    assert [reason.key for reason in result.reasons] == ["terms:kind:add", None]
    assert result.script is not None
    assert result.script.pr_url == "https://github.com/o/r/pull/9"
    assert result.base_commit == BASE_COMMIT


def test_to_conflict_when_script_missing() -> None:
    """スクリプトの指定が無い・差分確認（正常系）。"""
    # 準備
    conflict = {"branch": None, "commit": None, "baseCommit": BASE_COMMIT, "errors": [], "script": None}
    # 実行
    result = to_conflict(conflict, [])
    # 検証
    assert result.script is None
    assert result.branch is None


def test_to_conflict_when_no_pr_url() -> None:
    """最後の行が URL でない（正常系）。"""
    # 準備
    conflict = {
        "branch": "project-index/conflict/20261123-103000-0a1b2c3",
        "commit": "1b2c3d4",
        "baseCommit": BASE_COMMIT,
        "errors": [],
        "script": {"exitCode": 1, "timedOut": False, "stdout": "done", "stderr": "boom"},
    }
    # 実行
    result = to_conflict(conflict, [])
    # 検証
    assert result.script is not None
    assert result.script.pr_url is None
    assert result.script.exit_code == 1
