from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, Literal

import pytest

from dev_docs.features.convert.service import ConvertService
from dev_docs.features.metadata.commits import (
    CommitRequest,
    Edit,
    EditsRejectedError,
    check_edits,
    commit_edits,
    item_expected_versions,
    to_conflict,
    to_operations,
)
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.shared.errors import ProjectIndexTimeoutError

from ...conftest import FakeIndex, config_json, doc_json

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
    result = asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
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
        asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
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
        asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
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
        asyncio.run(commit_edits(client, "sample", request, convert=ConvertService()))
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
    asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
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
    asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
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
        asyncio.run(commit_edits(make_client(), "sample", _request(), convert=ConvertService()))
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
    result = asyncio.run(
        commit_edits(make_client(), "sample", _request(), convert=ConvertService())
    )
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
        {
            "path": "notes/n1.yaml",
            "itemVersions": {"name": "m1", "description": "d1", "tags": "t1"},
        },
    )
    mappings = {"note": {"tags": "tags[].name"}}
    # 実行
    versions = asyncio.run(item_expected_versions(make_client(), "sample", _request(), mappings))
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
    indexes: list[tuple[Literal["write", "delete"], int, str]] = [
        ("write", 0, "tags:n1:update"),
        ("write", 1, "terms:kind:add"),
    ]
    # 実行
    result = to_conflict(conflict, indexes, _edits())
    # 検証
    assert [reason.key for reason in result.reasons] == ["terms:kind:add", None]
    assert result.script is not None
    assert result.script.pr_url == "https://github.com/o/r/pull/9"
    assert result.base_commit == BASE_COMMIT


def test_to_conflict_when_version_mismatch() -> None:
    """文書の ID の理由をその文書の変更へ戻す（正常系）。"""
    # 準備
    conflict: dict[str, Any] = {
        "branch": "project-index/conflict/20261123-103000-0a1b2c3",
        "commit": "1b2c3d4",
        "baseCommit": BASE_COMMIT,
        "errors": [{"path": "n1", "reason": "n1 は参照した後に変わっています"}],
        "script": None,
    }
    edits = _edits()[:2]
    indexes: list[tuple[Literal["write", "delete"], int, str]] = [
        ("write", 0, "tags:n1:update"),
        ("write", 1, "terms:kind:add"),
    ]
    # 実行
    result = to_conflict(conflict, indexes, edits)
    # 検証
    assert [(reason.key, reason.reason) for reason in result.reasons] == [
        ("tags:n1:update", "n1 は参照した後に変わっています")
    ]


def test_to_conflict_when_script_missing() -> None:
    """スクリプトの指定が無い・差分確認（正常系）。"""
    # 準備
    conflict: dict[str, Any] = {
        "branch": None,
        "commit": None,
        "baseCommit": BASE_COMMIT,
        "errors": [],
        "script": None,
    }
    # 実行
    result = to_conflict(conflict, [], [])
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
    result = to_conflict(conflict, [], [])
    # 検証
    assert result.script is not None
    assert result.script.pr_url is None
    assert result.script.exit_code == 1


def test_item_expected_versions_when_key_missing(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """編集を始めたときの文書に修正したキーが無い（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[N1_PATH] = (
        200,
        {"path": "notes/n1.yaml", "itemVersions": {"id": "i1", "name": "m1"}},
    )
    # 実行
    versions = asyncio.run(item_expected_versions(make_client(), "sample", _request(), {}))
    # 検証
    assert versions == {"tags:n1:update": "c3d4e5"}


def test_item_expected_versions_when_base_commit_missing(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """編集を始めたときのコミットがクローンに無い（異常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[N1_PATH] = (
        404,
        {"missing": "ref", "value": BASE_COMMIT, "argument": "ref", "detail": ""},
    )
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(item_expected_versions(make_client(), "sample", _request(), {}))
    # 検証
    assert caught.value.status_code == 409
    assert caught.value.name == "BaseCommitUnusableError"
    assert caught.value.errors == []


def _body_edit(key: str, path: str, value: Any, *, doc_path: str = "notes/n1.yaml") -> Edit:
    """文書 n1 の本文の変更を作る。"""
    return Edit(
        key=key,
        kind="body",
        op="update",
        doc_id="n1",
        doc_kind="note",
        expected_version="c3d4e5",
        doc_path=doc_path,
        values={path: value},
    )


def test_to_operations_when_body() -> None:
    """本文の変更を変換する（正常系）。"""
    # 準備
    edits = [
        _body_edit("body:n1:#items[i1].body", "#items[i1].body", "修正後の本文"),
        _body_edit("body:n1:@file", "@file", "id: n1\nname: 修正後\n"),
        _body_edit("body:guide:@file", "@file", "# 修正後\n", doc_path="guide.md"),
    ]
    versions: dict[str, dict[str, str] | str] = {
        "body:n1:#items[i1].body": {"items": "t1"},
        "body:n1:@file": "c3d4e5",
        "body:guide:@file": "c3d4e5",
    }
    # 実行
    writes, _, _ = to_operations(edits, {}, versions)
    # 検証
    assert writes == [
        {
            "op": "update",
            "id": "n1",
            "expected_version": {"items": "t1"},
            "set": {"#items[i1].body": "修正後の本文"},
        },
        {
            "op": "replace",
            "id": "n1",
            "expected_version": "c3d4e5",
            "data": {"id": "n1", "name": "修正後"},
        },
        {
            "op": "update",
            "id": "n1",
            "expected_version": "c3d4e5",
            "set": {"@body": "# 修正後\n"},
        },
    ]


def test_to_operations_when_whole_file_unparsable() -> None:
    """読み込めないファイル全体（異常系）。"""
    # 準備
    edit = _body_edit("body:n1:@file", "@file", "id: n1\nname: a\n\tsummary: b\n")
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        to_operations([edit], {}, {"body:n1:@file": "c3d4e5"})
    # 検証
    assert caught.value.status_code == 400
    assert caught.value.errors[0].path == "@file"
    assert "3" in caught.value.errors[0].reason


@pytest.mark.parametrize(
    ("target", "docs"),
    [
        pytest.param(
            ("body:n1:#items[x].id", "#items[x].id", "x2", "notes/n1.yaml"),
            [
                {
                    "id": "n1",
                    "path": "notes/n1.yaml",
                    "kind": "note",
                    "value": {"id": "n1", "name": "m1"},
                }
            ],
            id="unknown-path",
        ),
        pytest.param(
            ("body:tool:@file", "@file", "x = 2\n", "tool.py"),
            [
                {
                    "id": "n1",
                    "path": "docs/files.yml",
                    "kind": "files",
                    "bodyPath": "tool.py",
                    "value": {"path": "tool.py"},
                }
            ],
            id="not-editable",
        ),
    ],
)
def test_commit_edits_when_body_path_unknown(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    target: tuple[str, str, str, str],
    docs: list[dict[str, Any]],
) -> None:
    """修正できない項目のパス（異常系）。"""
    # 準備
    key, path, value, doc_path = target
    edit = _body_edit(key, path, value, doc_path=doc_path)
    _prepare(fake_index, 200, {"applied": True, "results": [], "commit": None})
    fake_index.configs["sample"] = config_json(
        documents=[
            *CONFIG_ROWS,
            {"id": "files", "paths": ["docs/files.yml"], "records": "files"},
        ]
    )
    fake_index.docs["sample"] = {
        BASE_COMMIT: [
            {**doc_json(item["id"], item["path"], kind=item["kind"]), **item} for item in docs
        ]
    }
    fake_index.responses.pop(N1_PATH)
    request = _request(edits=[edit])
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        asyncio.run(commit_edits(make_client(), "sample", request, convert=ConvertService()))
    # 検証
    assert caught.value.status_code == 400
    assert not any(item.url.path.endswith("/commits") for item in fake_index.requests)


def test_item_expected_versions_when_body(
    fake_index: FakeIndex, make_client: Callable[..., ProjectIndexClient]
) -> None:
    """本文の変更の最上位のキー（正常系）。"""
    # 準備
    fake_index.configs["sample"] = config_json(documents=CONFIG_ROWS)
    fake_index.responses[N1_PATH] = (
        200,
        {"path": "notes/n1.yaml", "itemVersions": {"items": "t-items", "name": "m1"}},
    )
    request = _request(
        edits=[
            _body_edit("body:n1:#items[i1].body", "#items[i1].body", "修正後"),
            _body_edit("body:n2:@file", "@file", "id: n2\n", doc_path="notes/n2.yaml").model_copy(
                update={"doc_id": "n2"}
            ),
        ]
    )
    # 実行
    versions = asyncio.run(item_expected_versions(make_client(), "sample", request, {}))
    # 検証
    assert versions == {"body:n1:#items[i1].body": {"items": "t-items"}, "body:n2:@file": "c3d4e5"}


def test_check_edits() -> None:
    """修正できる列と本文の変更（正常系）。"""
    # 準備
    edits = [
        *_edits()[:2],
        _body_edit("body:n1:summary", "summary", "修正後"),
        _body_edit(
            "body:n2:@file", "@file", "id: n2\nname: 修正後\n", doc_path="notes/n2.yaml"
        ).model_copy(update={"doc_id": "n2"}),
    ]
    # 実行・検証（例外を送出しない）
    check_edits(edits)


@pytest.mark.parametrize("column", ["description", "path"])
def test_check_edits_when_column_not_editable(column: str) -> None:
    """種類に無い列と修正できない列（異常系）。"""
    # 準備
    edit = _edits()[0].model_copy(update={"values": {column: "notes/n1.yaml"}})
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        check_edits([edit])
    # 検証
    assert caught.value.status_code == 400
    assert [(item.key, item.path) for item in caught.value.errors] == [("tags:n1:update", column)]


def test_check_edits_when_whole_file_mixed() -> None:
    """同じ文書のファイル全体と項目の変更（異常系）。"""
    # 準備
    edits = [
        _body_edit("body:n1:@file", "@file", "id: n1\n"),
        _body_edit("body:n1:summary", "summary", "修正後"),
    ]
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        check_edits(edits)
    # 検証
    assert caught.value.status_code == 400
    assert sorted(str(item.key) for item in caught.value.errors) == [
        "body:n1:@file",
        "body:n1:summary",
    ]


def test_check_edits_when_whole_file_unparsable() -> None:
    """読み込めないファイル全体（異常系）。"""
    # 準備
    edit = _body_edit("body:n1:@file", "@file", "id: n1\nname: m1\n\tsummary: 概要\n")
    # 実行
    with pytest.raises(EditsRejectedError) as caught:
        check_edits([edit])
    # 検証
    assert caught.value.status_code == 400
    [error] = caught.value.errors
    assert error.path == "@file"
    assert "3" in error.reason


def test_commit_edits_when_replaced(
    fake_index: FakeIndex,
    make_client: Callable[..., ProjectIndexClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ファイル全体の置き換えの結果（正常系）。"""
    # 準備
    edit = _body_edit("body:n1:@file", "@file", "id: n1\nname: 修正後\n")
    result = {"kind": "write", "index": 0, "id": "n1", "status": "replaced", "version": "v2"}
    _prepare(fake_index, 200, {"applied": True, "results": [result], "commit": None})

    async def _allowed(*_: Any, **__: Any) -> None:
        return None

    # 修正できる項目のパスの確認は test_commit_edits_when_body_path_unknown が確かめる
    monkeypatch.setattr("dev_docs.features.metadata.commits._check_body_paths", _allowed)
    # 実行
    committed = asyncio.run(
        commit_edits(make_client(), "sample", _request(edits=[edit]), convert=ConvertService())
    )
    # 検証
    assert [(item.key, item.status) for item in committed.results] == [("body:n1:@file", "updated")]
