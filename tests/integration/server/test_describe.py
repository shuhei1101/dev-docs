from __future__ import annotations

from collections.abc import Callable
from typing import Any

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
INSTRUCTIONS = "この配信元の文書は、まず概要を読んでから個別の文書を開く。"


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
