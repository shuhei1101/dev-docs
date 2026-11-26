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
    body_source,
    metadata_source,
    note_value,
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


def _base(env: ServerEnv) -> str:
    """メタデータの取得の `baseCommit`（編集を始めたときのコミット）。"""
    return str(env.client.get(METADATA_URL).json()["baseCommit"])


def _push_other(source: DirectSource, workdir: Path, path: str, value: dict[str, Any]) -> str:
    """ほかの変更として、リモートの develop の文書を書き換えるコミットをプッシュし、そのコミットを返却する。"""
    other = workdir / "other"
    if not other.exists():
        _git(workdir, "clone", "-q", "-b", "develop", str(source.bare), str(other))
    (other / path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    _git(other, "commit", "-qam", "other")
    _git(other, "push", "-q", "origin", "develop")
    return _git(source.bare, "rev-parse", "develop")


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
        "docPath": row["docPath"],
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
    body = {"edits": _edits(env), "message": MESSAGE, "baseCommit": _base(env)}
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
    assert data["conflict"] is None
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
    body = {"edits": _edits(env), "dryRun": True, "baseCommit": _base(env)}
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
    body = {"edits": _edits(env), "message": MESSAGE, "baseCommit": _base(env)}
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
        "docPath": "notes/n1.yaml",
        "values": {"description": "説明"},
    }
    # 実行
    invalid_key = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": "0a1b2c3"},
        headers=SAME_ORIGIN,
    )
    empty_message = env.client.post(
        URL,
        json={
            "edits": [{**edit, "values": {"tags": ["topic:a"]}}],
            "message": "",
            "baseCommit": "0a1b2c3",
        },
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
    response = env.client.post(
        URL,
        json={"edits": edits, "message": MESSAGE, "baseCommit": _base(env)},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 422, data
    errors = [item for item in data["errors"] if item.get("key") == "tags:n1:update"]
    assert errors
    assert any("tags" in str(item.get("path")) for item in errors)
    assert "terms:kind:add" not in {item.get("key") for item in data["errors"]}
    assert _state(source) == before


def test_error_when_base_commit_unusable(
    write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """編集を始めたときのコミットがクローンに無いときは 409 で断り、何もコミットしない（異常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    before = _state(source)
    # 実行
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": "deadbeefdeadbeef"},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 409, data
    assert data["title"] == "BaseCommitUnusableError"
    assert data["errors"] == []
    assert _state(source) == before


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
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": _base(env)},
        headers=SAME_ORIGIN,
    )
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
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": _base(env)},
        headers=SAME_ORIGIN,
    )
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
        "docPath": "notes/n1.yaml",
        "values": {"tags": ["topic:a"]},
    }
    mock_index.queued[("GET", "/sources/sample/docs/notes/n1.yaml")] = [
        (200, {"path": "notes/n1.yaml", "itemVersions": {"tags": "t1"}})
    ]
    started = time.monotonic()
    # 実行
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": "0a1b2c3"},
        headers=SAME_ORIGIN,
    )
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
        "docPath": row["docPath"],
        "values": {"tags": ["topic:a", "topic:b"]},
    }
    # 実行
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": _base(env)},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    written = _remote_file(source, "docs/rule/r1.yaml")
    assert response.status_code == 200, data
    assert data["applied"] is True
    assert written["tags"] == [{"name": "topic:a", "main": True}, {"name": "topic:b"}]
    assert sorted(written) == ["id", "name", "tags"]


# 衝突したときのスクリプトの偽物: 受けた環境変数を記録し、標準出力の最後の行に PR の URL を出す
CONFLICT_SCRIPT = """#!/bin/sh
env | grep '^PROJECT_INDEX_' | sort > "$(dirname "$0")/received.env"
echo "pushed"
echo "https://github.com/o/r/pull/9"
"""
# 失敗する衝突したときのスクリプトの偽物
FAILING_SCRIPT = """#!/bin/sh
echo "gh: authentication required" >&2
exit 1
"""


def _script(workdir: Path, text: str) -> list[str]:
    """衝突したときのスクリプトの偽物を書き込み、`on_conflict.command` を返却する。"""
    path = workdir / "on-conflict.sh"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return ["/bin/sh", str(path)]


def _n1(**values: Any) -> dict[str, Any]:
    """文書 n1 の値。"""
    return {"id": "n1", "name": "メモ", "tags": ["topic:a"], **values}


def test_normal_when_other_item_changed(
    write_index: RealIndex, make_server: Callable[..., ServerEnv], tmp_path: Path
) -> None:
    """同じ文書の別の項目が変わっていても、修正した項目が重ならなければコミットする（正常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    base = _base(env)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    pushed = _push_other(source, tmp_path, "notes/n1.yaml", _n1(description="ほかの変更"))
    # 実行
    response = env.client.post(
        URL, json={"edits": [edit], "message": MESSAGE, "baseCommit": base}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["applied"] is True
    assert data["conflict"] is None
    assert _git(source.bare, "rev-parse", "develop~1") == pushed
    written = _remote_file(source, "notes/n1.yaml")
    assert written["description"] == "ほかの変更"
    assert written["tags"] == ["topic:a", "topic:b"]


def test_normal_when_conflict_kept_on_branch(
    tmp_path: Path, write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """同じ項目が変わっていたら、修正をブランチに残してスクリプトの PR の URL を返却する（正常系）。"""
    # 準備
    source = metadata_source(write_index, on_conflict=_script(tmp_path, CONFLICT_SCRIPT))
    env = make_server(write_index)
    base = _base(env)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    pushed = _push_other(source, tmp_path, "notes/n1.yaml", _n1(tags=["topic:x"]))
    # 実行
    response = env.client.post(
        URL, json={"edits": [edit], "message": MESSAGE, "baseCommit": base}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["applied"] is False
    conflict = data["conflict"]
    assert conflict["branch"].startswith("project-index/conflict/")
    assert conflict["baseCommit"].startswith(base)
    assert [reason["key"] for reason in conflict["reasons"]] == ["tags:n1:update"]
    assert conflict["script"]["exitCode"] == 0
    assert conflict["script"]["prUrl"] == "https://github.com/o/r/pull/9"
    assert _git(source.bare, "rev-parse", "develop") == pushed
    assert _git(source.repo, "rev-parse", f"{conflict['branch']}~1").startswith(base)
    received = (tmp_path / "received.env").read_text(encoding="utf-8")
    assert f"PROJECT_INDEX_CONFLICT_BRANCH={conflict['branch']}" in received
    assert f"PROJECT_INDEX_COMMIT_MESSAGE={MESSAGE}" in received


def test_normal_when_conflict_script_not_configured(
    tmp_path: Path, write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """衝突したときのスクリプトの指定が無いときは、ブランチだけを残して script を null にする（正常系）。"""
    # 準備
    source = metadata_source(write_index)
    env = make_server(write_index)
    base = _base(env)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    pushed = _push_other(source, tmp_path, "notes/n1.yaml", _n1(tags=["topic:x"]))
    # 実行
    response = env.client.post(
        URL, json={"edits": [edit], "message": MESSAGE, "baseCommit": base}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["conflict"]["branch"].startswith("project-index/conflict/")
    assert data["conflict"]["script"] is None
    assert _git(source.bare, "rev-parse", "develop") == pushed


def test_normal_when_conflict_script_failed(
    tmp_path: Path, write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """衝突したときのスクリプトが失敗しても、ブランチを残して終了コードと標準エラー出力を返却する（正常系）。"""
    # 準備
    source = metadata_source(write_index, on_conflict=_script(tmp_path, FAILING_SCRIPT))
    env = make_server(write_index)
    base = _base(env)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    _push_other(source, tmp_path, "notes/n1.yaml", _n1(tags=["topic:x"]))
    # 実行
    response = env.client.post(
        URL, json={"edits": [edit], "message": MESSAGE, "baseCommit": base}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    script = data["conflict"]["script"]
    assert response.status_code == 200, data
    assert data["conflict"]["branch"].startswith("project-index/conflict/")
    assert script["exitCode"] == 1
    assert script["prUrl"] is None
    assert "authentication required" in script["stderr"]


def test_normal_when_dry_run_conflicted(
    tmp_path: Path, write_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """差分確認で衝突するときは、ブランチを作らずに断る理由を返却する（正常系）。"""
    # 準備
    source = metadata_source(write_index, on_conflict=_script(tmp_path, CONFLICT_SCRIPT))
    env = make_server(write_index)
    base = _base(env)
    edit = _tag_edit(env, ["topic:a", "topic:b"])
    # 差分確認はリモートを取得しないため、ほかの変更は project-index のクローンに入れる
    other = env.client.post(
        URL,
        json={"edits": [_tag_edit(env, ["topic:x"])], "message": MESSAGE, "baseCommit": base},
        headers=SAME_ORIGIN,
    )
    assert other.status_code == 200, other.json()
    branches = _git(source.repo, "branch", "--list", "project-index/conflict/*")
    # 実行
    response = env.client.post(
        URL, json={"edits": [edit], "dryRun": True, "baseCommit": base}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["conflict"]["branch"] is None
    assert data["conflict"]["script"] is None
    assert [reason["key"] for reason in data["conflict"]["reasons"]] == ["tags:n1:update"]
    assert _git(source.repo, "branch", "--list", "project-index/conflict/*") == branches
    assert not (tmp_path / "received.env").exists()


def _doc_edit(env: ServerEnv, path: str) -> dict[str, Any]:
    """文書の取得の `edit`（本文の編集の情報）。"""
    return dict(env.client.get(f"/_api/sources/sample/docs/{path}").json()["edit"])


def _body_edit(edit: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """文書の取得の `edit` から、本文の項目のパスかファイル全体の変更を作る。"""
    return {
        "key": f"body:{edit['docId']}:{path}",
        "kind": "body",
        "op": "update",
        "docId": edit["docId"],
        "docKind": edit["kind"],
        "expectedVersion": edit["version"],
        "docPath": edit["filePath"],
        "values": {path: value},
    }


def _replaced(edit: dict[str, Any], old: str, new: str) -> str:
    """ファイル全体の元の内容の 1 か所を書き換える。"""
    assert old in edit["source"]
    return str(edit["source"]).replace(old, new, 1)


def test_normal_when_document_body_edited(
    body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """項目のパスへの修正とファイル全体の編集を 1 つのコミットにしてプッシュする（正常系）。"""
    # 準備
    source = body_source(body_index)
    env = make_server(body_index)
    n1 = _doc_edit(env, "notes/n1")
    n2 = _doc_edit(env, "notes/n2")
    guide = _doc_edit(env, "files/guide.md")
    rows = [{"word": "a", "replacement": "b"}, {"word": "c", "replacement": "e"}]
    guide_body = guide["source"].replace("1 行目の説明", "修正後の説明")
    edits = [
        _body_edit(n1, "summary", "修正後の概要"),
        _body_edit(n1, "rows", rows),
        _body_edit(n1, "#items[i1].body", "修正後の本文"),
        _body_edit(n2, "@file", _replaced(n2, "summary: 概要", "summary: 修正後")),
        _body_edit(guide, "@file", guide_body),
    ]
    before = _git(source.bare, "rev-parse", "develop")
    # 実行
    response = env.client.post(
        URL,
        json={"edits": edits, "message": MESSAGE, "baseCommit": n1["baseCommit"]},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["applied"] is True
    assert sorted((item["key"], item["status"]) for item in data["results"]) == sorted(
        (edit["key"], "updated") for edit in edits
    )
    assert _git(source.bare, "rev-parse", "develop~1") == before
    changed = _git(source.bare, "diff", "--name-only", f"{before}..develop").splitlines()
    assert sorted(changed) == ["guide.md", "notes/n1.yaml", "notes/n2.yaml"]
    written = _remote_file(source, "notes/n1.yaml")
    assert written == note_value(
        "n1", summary="修正後の概要", rows=rows, items=[{"id": "i1", "body": "修正後の本文"}]
    )
    assert _remote_file(source, "notes/n2.yaml")["summary"] == "修正後"
    assert _git(source.bare, "show", "develop:guide.md") == guide_body.rstrip("\n")


def test_normal_when_whole_file_edit_conflicted(
    tmp_path: Path, body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """ファイル全体の変更の後に同じ文書の別の項目が変わっていれば、修正をブランチに残す（正常系）。"""
    # 準備
    source = body_source(body_index, on_conflict=_script(tmp_path, CONFLICT_SCRIPT))
    env = make_server(body_index)
    n1 = _doc_edit(env, "notes/n1")
    edit = _body_edit(n1, "@file", _replaced(n1, "summary: 概要", "summary: 修正後"))
    pushed = _push_other(
        source,
        tmp_path,
        "notes/n1.yaml",
        note_value("n1", rows=[{"word": "x", "replacement": "y"}]),
    )
    # 実行
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": n1["baseCommit"]},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 200, data
    assert data["applied"] is False
    conflict = data["conflict"]
    assert conflict["branch"].startswith("project-index/conflict/")
    assert [reason["key"] for reason in conflict["reasons"]] == [edit["key"]]
    assert conflict["script"]["prUrl"] == "https://github.com/o/r/pull/9"
    assert _git(source.bare, "rev-parse", "develop") == pushed


def test_error_when_whole_file_unparsable(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """YAML として読み込めない @file を、project-index へ送信せずに断る（異常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource())
    env = make_server(mock_index)
    edit = {
        "key": "body:n2:@file",
        "kind": "body",
        "op": "update",
        "docId": "n2",
        "docKind": "note",
        "expectedVersion": "v1",
        "docPath": "notes/n2.yaml",
        "values": {"@file": "id: n2\ntitle: メモ\n\tsummary: 概要\n"},
    }
    # 実行
    response = env.client.post(
        URL,
        json={"edits": [edit], "message": MESSAGE, "baseCommit": "0a1b2c3"},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 400, data
    [error] = data["errors"]
    assert (error["key"], error["path"]) == ("body:n2:@file", "@file")
    assert "3" in error["reason"]
    assert not [item for item in mock_index.received if item[1].endswith("/commits")]


def test_error_when_document_body_invalid(
    body_index: RealIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """ファイル全体の変更の検査の違反を、変更の key と項目のパスで返却する（異常系）。"""
    # 準備
    source = body_source(body_index)
    env = make_server(body_index)
    n1 = _doc_edit(env, "notes/n1")
    guide = _doc_edit(env, "files/guide.md")
    edits = [
        _body_edit(n1, "@file", _replaced(n1, "summary: 概要", "summary: ''")),
        _body_edit(guide, "@file", guide["source"] + "追記\n"),
    ]
    before = _state(source)
    # 実行
    response = env.client.post(
        URL,
        json={"edits": edits, "dryRun": True, "baseCommit": n1["baseCommit"]},
        headers=SAME_ORIGIN,
    )
    # 検証
    data = response.json()
    assert response.status_code == 422, data
    keys = {item.get("key") for item in data["errors"]}
    assert edits[0]["key"] in keys
    assert any(
        item.get("key") == edits[0]["key"] and "summary" in str(item.get("path"))
        for item in data["errors"]
    )
    assert edits[1]["key"] not in keys
    assert _state(source) == before


def test_error_when_whole_file_and_item_edits_mixed(
    mock_index: MockIndex, make_server: Callable[..., ServerEnv]
) -> None:
    """同じ文書の @file と項目のパスの変更が並ぶ要求を、project-index へ送信せずに断る（異常系）。"""
    # 準備
    mock_index.serve("sample", IndexSource())
    env = make_server(mock_index)
    common = {
        "kind": "body",
        "op": "update",
        "docId": "n1",
        "docKind": "note",
        "expectedVersion": "v1",
        "docPath": "notes/n1.yaml",
    }
    edits = [
        {**common, "key": "body:n1:@file", "values": {"@file": "id: n1\ntitle: メモ\n"}},
        {**common, "key": "body:n1:summary", "values": {"summary": "修正後"}},
    ]
    # 実行
    response = env.client.post(
        URL, json={"edits": edits, "message": MESSAGE, "baseCommit": "0a1b2c3"}, headers=SAME_ORIGIN
    )
    # 検証
    data = response.json()
    assert response.status_code == 400, data
    assert {item["key"] for item in data["errors"]} == {"body:n1:@file", "body:n1:summary"}
    assert not [item for item in mock_index.received if item[1].endswith("/commits")]
