from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
INSTRUCTIONS = "この配信元の文書は、まず概要を読んでから個別の文書を開く。"
OUTSIDE_LINE = "作業範囲の外（参考）"
OUTSIDE_LOG = "作業範囲の外を読んだ"
OUTSIDE_HINT = "outside_scope: true"


def test_normal(make_source: Callable[..., Any], make_server: Callable[..., Any]) -> None:
    """引数なしで、今の作業場所から使える配信元の一覧を返す（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    other = make_source("other")
    env = make_server(sample, notes, other)
    # 実行
    result = env.call("describe", cwd=str(sample.folder))
    # 検証
    assert not result.is_error
    assert result.text.startswith(f"作業場所: {sample.folder}")
    assert "sample のクローン本体" in result.text.splitlines()[0]
    assert "| sample | write（作業中） |" in result.text
    assert "| notes | read |" in result.text
    assert "| other |" not in result.text


def test_normal_when_source(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """source で配信元の説明書と種類の一覧を返す（正常系）。"""
    # 準備
    config = sample_config_text("instructions: |-\n  " + INSTRUCTIONS + "\n")
    sample = make_source("sample", sample_file_set(**{"dev-docs.yaml": config}))
    env = make_server(sample)
    # 実行
    result = env.call("describe", cwd=str(sample.folder), source="sample")
    # 検証
    assert INSTRUCTIONS in result.text
    assert "| sample |" in result.text


def test_normal_when_kind(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """source と kind で種類のスキーマと、共通のキーと列名の対応を返す（正常系）。"""
    # 準備
    extra = (
        "    metadata: {name: title, description: meta.summary}\n"
        "  - id: plain\n"
        "    paths: [plain/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
    )
    files = sample_file_set(**{"dev-docs.yaml": sample_config_text(extra)})
    sample = make_source("sample", files)
    env = make_server(sample)
    schema = (sample.folder / "schemas" / "sample.schema.yaml").read_text(encoding="utf-8")
    # 実行
    markdown = env.call("describe", cwd=str(sample.folder), source="sample", kind="sample")
    as_json = env.call(
        "describe", cwd=str(sample.folder), source="sample", kind="sample", format="json"
    )
    plain_markdown = env.call("describe", cwd=str(sample.folder), source="sample", kind="plain")
    plain_json = env.call(
        "describe", cwd=str(sample.folder), source="sample", kind="plain", format="json"
    )
    # 検証
    assert schema.strip() in markdown.text
    assert "| name | title |" in markdown.text
    assert "| description | meta.summary |" in markdown.text
    assert markdown.text.index("| name | title |") < markdown.text.index(schema.strip())
    assert as_json.structured is not None
    assert as_json.structured == as_json.data
    assert as_json.data["schema"]["properties"]["name"]["type"] == "string"
    assert as_json.data["metadata"] == {"name": "title", "description": "meta.summary"}
    assert "共通のキー" not in plain_markdown.text
    assert plain_json.data.get("metadata", {}) == {}


def test_error_when_source_not_readable(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """scope に当たらない配信元の説明を断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    other = make_source(
        "other",
        {
            "dev-docs.yaml": "name: other\ninstructions: 秘密の説明書\n"
            "documents:\n  - id: sample\n    paths: [docs/*.yaml]\n"
            "    schema: schemas/sample.schema.yaml\n",
            "schemas/sample.schema.yaml": "type: object\n",
            "docs/doc-1.yaml": "id: doc-1\n",
        },
    )
    env = make_server(sample, other)
    # 実行
    result = env.call("describe", cwd=str(sample.folder), source="other")
    listed = env.call("describe", cwd=str(sample.folder))
    # 検証
    assert result.is_error
    assert "SourceNotReadableError" in result.text
    assert "other" in result.text
    assert "source_id: sample" in result.text
    assert "access: write" in result.text
    assert "source_id: other" not in result.text
    assert "秘密の説明書" not in result.text
    assert "| sample | write（作業中） |" in listed.text


def test_error_when_source_not_served(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """起動時の検証で外した配信元の説明を断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, scope_read=[sample.folder])
    env = make_server(sample, broken)
    # 実行
    result = env.call("describe", cwd=str(sample.folder), source="broken")
    listed = env.call("describe", cwd=str(sample.folder))
    # 検証
    assert result.is_error
    assert "SourceNotServedError" in result.text
    assert "broken" in result.text
    assert "documents[0].paths" in result.text
    assert "| broken |" not in listed.text


def test_error_when_unknown_kind(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """配信元に無い kind を断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    env = make_server(sample)
    # 実行
    result = env.call("describe", cwd=str(sample.folder), source="sample", kind="no-such-kind")
    # 検証
    assert result.is_error
    assert "UnknownKindError" in result.text
    assert "no-such-kind" in result.text
    assert "sample" in result.text


def _outside_logs(caplog: pytest.LogCaptureFixture) -> list[str]:
    """要求のログのうち作業範囲の外を読んだ記録を返す。"""
    return [record.getMessage() for record in caplog.records if OUTSIDE_LOG in record.getMessage()]


def test_normal_when_outside_scope(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """outside_scope: true で、scope に当たらない配信元の説明書を作業範囲の外として返す（正常系）。"""
    # 準備
    config = sample_config_text("instructions: |-\n  " + INSTRUCTIONS + "\n", name="other")
    sample = make_source("sample")
    other = make_source("other", sample_file_set(**{"dev-docs.yaml": config}))
    env = make_server(sample, other)
    cwd = str(sample.folder)
    caplog.set_level(logging.INFO)
    # 実行
    result = env.call("describe", cwd=cwd, source="other", outside_scope=True)
    as_json = env.call("describe", cwd=cwd, source="other", outside_scope=True, format="json")
    logged = _outside_logs(caplog)
    caplog.clear()
    inside = env.call("describe", cwd=cwd, source="sample", outside_scope=True, format="json")
    inside_logs = _outside_logs(caplog)
    listed = env.call("describe", cwd=cwd)
    # 検証
    lines = result.text.splitlines()
    assert not result.is_error
    assert lines[0] == OUTSIDE_LINE
    assert INSTRUCTIONS in result.text
    assert "| sample |" in result.text
    assert as_json.data["outside_scope"] is True
    assert any(cwd in message and "other" in message for message in logged)
    assert not inside.data.get("outside_scope")
    assert inside_logs == []
    assert "| other |" not in listed.text


def test_error_when_outside_read_disabled(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """outside_read: false の配信元は outside_scope: true でも断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    closed = make_source("other", outside_read=False)
    opened = make_source("open")
    env = make_server(sample, closed, opened)
    cwd = str(sample.folder)
    caplog.set_level(logging.INFO)
    # 実行
    refused = env.call("describe", cwd=cwd, source="other", outside_scope=True)
    guided = env.call("describe", cwd=cwd, source="open")
    # 検証
    assert refused.is_error
    assert "SourceNotReadableError" in refused.text
    assert "other" in refused.text
    assert OUTSIDE_HINT not in refused.text
    assert _outside_logs(caplog) == []
    assert guided.is_error
    assert OUTSIDE_HINT in guided.text


def test_normal_when_refs_and_worktrees(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    run_git: Callable[..., str],
    add_worktree: Callable[..., Any],
) -> None:
    """source で、ブランチ・タグとワークツリーの一覧を返す（正常系）。"""
    # 準備
    sample = make_source("sample")
    run_git(sample.folder, "tag", "v0.1.0")
    worktree = add_worktree(sample.folder, "x")
    outside = sample.folder.parent / "outside"
    run_git(sample.folder, "worktree", "add", "-b", "feat/y", str(outside))
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    env = make_server(sample, notes)
    cwd = str(sample.folder)
    # 実行
    result = env.call("describe", cwd=cwd, source="sample", format="json")
    plain = env.call("describe", cwd=cwd, source="notes", format="json")
    # 検証
    worktrees = {item["path"]: item.get("branch") for item in result.data["worktrees"]}
    assert {"develop", "feat/x"} <= set(result.data["refs"]["branches"])
    assert "v0.1.0" in result.data["refs"]["tags"]
    assert worktrees == {str(worktree): "feat/x"}
    assert "refs" not in plain.data
    assert "worktrees" not in plain.data
