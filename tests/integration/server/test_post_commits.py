from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from .conftest import (
    SAME_ORIGIN,
    DirectSource,
    IndexSource,
    MockIndex,
    RealIndex,
    ServerEnv,
    metadata_source,
)

URL = "/_api/sources/sample/commits"
METADATA_URL = "/_api/sources/sample/metadata"
MESSAGE = "用語とタグを修正する"


def _git(cwd: Path, *args: str) -> str:
    """git を実行して標準出力を返却する。"""
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _state(source: DirectSource) -> tuple[str, str, str]:
    """リモートの develop・develop のワークツリーの HEAD・git status の組を返却する。"""
    return (
        _git(source.bare, "rev-parse", "develop"),
        _git(source.develop, "rev-parse", "HEAD"),
        _git(source.develop, "status", "--porcelain"),
    )


def _row(env: ServerEnv, kind_id: str, row_id: str) -> dict[str, Any]:
    """メタデータの取得から、種類の行 1 つを取り出す。"""
    body = env.client.get(METADATA_URL).json()
    kind = next(item for item in body["kinds"] if item["id"] == kind_id)
    return next(row for row in kind["rows"] if row["id"] == row_id)


def _tag_edit(env: ServerEnv, tags: list[str]) -> dict[str, Any]:
    """n1 のタグの update。"""
    row = _row(env, "tags", "n1")
    return {
        "key": "tags:n1:update",
        "kind": "tags",
        "op": "update",
        "docId": "n1",
        "docKind": row["docKind"],
        "expectedVersion": row["version"],
        "values": {"tags": tags},
    }


def _edits(env: ServerEnv) -> list[dict[str, Any]]:
    """n1 のタグの update・用語 kind の add・用語 old-name の delete。"""
    old = _row(env, "terms", "old-name")
    return [
        _tag_edit(env, ["topic:a", "topic:b"]),
        {
            "key": "terms:kind:add",
            "kind": "terms",
            "op": "add",
            "docId": "kind",
            "docKind": "terms",
            "values": {"name": "種類", "description": "文書の行の ID"},
        },
        {
            "key": "terms:old-name:delete",
            "kind": "terms",
            "op": "delete",
            "docId": "old-name",
            "docKind": "terms",
            "expectedVersion": old["version"],
        },
    ]


def _remote_file(source: DirectSource, path: str) -> Any:
    """リモートの develop のファイルを JSON（YAML）として読み込む。"""
    from dev_docs.shared.yaml_io import load_yaml

    return load_yaml(_git(source.bare, "show", f"develop:{path}"))


def test_normal(write_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """変更を 1 つのコミットにしてプッシュし、変更ごとの結果とコミットを返却する（正常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    before = _git(source.bare, "rev-parse", "develop")
    body = {"edits": _edits(env), "message": MESSAGE}
    # 実行
    response = env.client.post(URL, json=body, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    after = _git(source.bare, "rev-parse", "develop")
    assert response.status_code == 200, data
    assert data["applied"] is True
    assert sorted((item["key"], item["status"]) for item in data["results"]) == [
        ("tags:n1:update", "updated"),
        ("terms:kind:add", "created"),
        ("terms:old-name:delete", "deleted"),
    ]
    assert data["commit"]["sha"] == after
    assert _git(source.bare, "rev-parse", f"{after}~1") == before
    assert _git(source.bare, "log", "-1", "--format=%s", "develop") == MESSAGE
    assert _remote_file(source, "notes/n1.yaml")["tags"] == ["topic:a", "topic:b"]
    terms = {item["id"] for item in _remote_file(source, "glossary.yaml")["terms"]}
    assert "kind" in terms
    assert "old-name" not in terms


def test_normal_when_dry_run(write_index: RealIndex, make_server: Callable[..., ServerEnv]) -> None:
    """dryRun は差分だけを返却し、コミットしない（正常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    body = {"edits": _edits(env), "dryRun": True}
    before = _state(source)
    # 実行
    response = env.client.post(URL, json=body, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert (data["applied"], data["commit"]) == (False, None)
    diffs = {item["key"]: item["diff"] for item in data["results"]}
    assert sorted(diffs) == ["tags:n1:update", "terms:kind:add", "terms:old-name:delete"]
    # 削除の diff は project-index が返却しない（空）
    assert diffs["tags:n1:update"]
    assert diffs["terms:kind:add"]
    assert _state(source) == before


def test_error_when_cross_origin(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """別のオリジンの要求は 403 で断る（異常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    body = {"edits": _edits(env), "message": MESSAGE}
    before = _state(source)
    # 実行
    response = env.client.post(URL, json=body, headers={"Origin": "http://127.0.0.1:9999"})
    # 検証
    assert response.status_code == 403
    assert _state(source) == before


def test_error_when_body_invalid(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """修正できないキーと空の説明は 400 で、project-index へ送信しない（異常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource())
    env = make_server(mock_index)
    edit = {
        "key": "tags:n1:update",
        "kind": "tags",
        "op": "update",
        "docId": "n1",
        "docKind": "note",
        "expectedVersion": "v1",
        "values": {"description": "説明"},
    }
    # 実行
    invalid_key = env.client.post(
        URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN
    )
    empty_message = env.client.post(
        URL,
        json={"edits": [{**edit, "values": {"tags": ["topic:a"]}}], "message": ""},
        headers=SAME_ORIGIN,
    )
    # 検証
    assert invalid_key.status_code == 400
    assert invalid_key.json()["errors"] == [
        {"key": "tags:n1:update", "path": "description", "reason": "この列は修正できません"}
    ]
    assert empty_message.status_code == 400
    assert "message" in json.dumps(empty_message.json(), ensure_ascii=False)
    assert not [item for item in mock_index.received if item[1].endswith("/commits")]


def test_error_when_validation_failed(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """検査に合格しない変更は 422 で、変更の key と違反したキーを返却する（異常系）。"""
    # 準備（note のスキーマはタグを `topic:` で始まる文字列に限る）
    source = metadata_source(write_index)
    env = make_server(write_index)
    edits = [
        {
            "key": "terms:kind:add",
            "kind": "terms",
            "op": "add",
            "docId": "kind",
            "docKind": "terms",
            "values": {"name": "種類"},
        },
        _tag_edit(env, ["topic:a", "使用できないタグ"]),
    ]
    before = _state(source)
    # 実行
    response = env.client.post(URL, json={"edits": edits, "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    assert response.status_code == 422, data
    errors = [item for item in data["errors"] if item.get("key") == "tags:n1:update"]
    assert errors
    assert any("tags" in str(item.get("path")) for item in errors)
    assert "terms:kind:add" not in {item.get("key") for item in data["errors"]}
    assert _state(source) == before


def test_error_when_version_mismatched(
    write_index: RealIndex,
    make_server: Callable[..., ServerEnv],
    tmp_path: Path,
) -> None:
    """取得した後に他の変更があった文書は 409 で、今のバージョンを返却する（異常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", "-b", "develop", str(source.bare), str(other))
    (other / "notes" / "n1.yaml").write_text(
        json.dumps({"id": "n1", "name": "メモ", "tags": ["topic:a"], "description": "他の変更"}),
        encoding="utf-8",
    )
    _git(other, "commit", "-qam", "other")
    _git(other, "push", "-q", "origin", "develop")
    pushed = _git(source.bare, "rev-parse", "develop")
    # 実行
    response = env.client.post(URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    assert response.status_code == 409, data
    [error] = [item for item in data["errors"] if item.get("key") == "tags:n1:update"]
    assert error["current"]
    assert error["current"] != edit["expectedVersion"]
    assert _git(source.bare, "rev-parse", "develop") == pushed


def test_error_when_direct_commit_not_permitted(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """write_api_kinds に無い種類を変える変更は 403 で断る（異常系）。"""
    # 準備
    source = metadata_source(write_index, write_api_kinds=["terms"])
    env = make_server(write_index)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    before = _state(source)
    # 実行
    response = env.client.post(URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    assert response.status_code == 403, data
    assert [item["key"] for item in data["errors"]] == ["tags:n1:update"]
    assert "note" in data["errors"][0]["reason"]
    assert "sources[].direct_commit.write_api_kinds" in " ".join(data["nextSteps"])
    assert _state(source) == before


def test_error_when_remote_unreachable(
    write_index: RealIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """リモートに接続できないときは 502 で、project-index の理由を返却する（異常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    _git(source.repo, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    # 実行
    response = env.client.post(URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    assert response.status_code == 502, data
    assert "project-index が" in data["detail"]
    assert _git(source.develop, "status", "--porcelain") == ""
    assert _git(source.develop, "log", "--oneline", "@{u}..HEAD") == ""


def test_error_when_write_timed_out(
    mock_index: MockIndex,
    make_server: Callable[..., ServerEnv],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """書き込みの API が待ちの上限までに応答しないときは 504 を返却する（異常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource())
    mock_index.path_delays["/sources/sample/commits"] = 3.0
    monkeypatch.setattr(
        "dev_docs.integrations.project_index.client.PROJECT_INDEX_WRITE_TIMEOUT_SEC", 1.0
    )
    env = make_server(mock_index)
    edit = {
        "key": "tags:n1:update",
        "kind": "tags",
        "op": "update",
        "docId": "n1",
        "docKind": "note",
        "expectedVersion": "v1",
        "values": {"tags": ["topic:a"]},
    }
    started = time.monotonic()
    # 実行
    response = env.client.post(URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    elapsed = time.monotonic() - started
    data = response.json()
    assert response.status_code == 504, data
    assert "コミットされたか" in data["detail"]
    assert any("再読み込み" in step for step in data["nextSteps"])
    assert elapsed < 2.0


def test_normal_when_tags_mapped(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """tags[].name に対応づけたタグは、main などのほかの項目を保って書き込む（正常系）。"""
    # 準備
    source = metadata_source(
        write_index,
        write_api_kinds=["note", "terms", "rule"],
        rule_tags=[{"name": "topic:a", "main": True}, {"name": "topic:c"}],
    )
    env = make_server(write_index)
    row = _row(env, "tags", "r1-rule")
    edit = {
        "key": "tags:r1-rule:update",
        "kind": "tags",
        "op": "update",
        "docId": "r1-rule",
        "docKind": row["docKind"],
        "expectedVersion": row["version"],
        "values": {"tags": ["topic:a", "topic:b"]},
    }
    # 実行
    response = env.client.post(URL, json={"edits": [edit], "message": MESSAGE}, headers=SAME_ORIGIN)
    # 検証
    data = response.json()
    written = _remote_file(source, "docs/rule/r1.yaml")
    assert response.status_code == 200, data
    assert data["applied"] is True
    assert written["tags"] == [{"name": "topic:a", "main": True}, {"name": "topic:b"}]
    assert sorted(written) == ["id", "name", "tags"]
