from __future__ import annotations

from collections.abc import Callable
from typing import Any

BROKEN_CONFIG = "name: sample\ndocuments:\n  - id: sample\n    type: yaml\n    schema: schemas/sample.schema.yaml\n"
CONVERT_OK = "import sys\nsys.stdin.read()\nprint('# 変換した')\n"
CONVERT_FAILING = "import sys\nprint('変換に失敗した', file=sys.stderr)\nsys.exit(3)\n"
CONVERTER_EXTRA = (
    "    converter: md\nconverters:\n  - id: md\n    run: [python3, scripts/convert.py]\n"
)
SYNC_ZERO = {"missing_refs": 0, "unindexed_files": 0, "missing_body_files": 0}


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_config_text: Callable[..., str],
    snapshot: Callable[..., dict[str, bytes]],
) -> None:
    """設定を変えて `check_project`・`try_convert` で確かめ、`reload` で配信に入れる（正常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    pid = served.call_admin("status", format="json").data["pid"]
    (sample.folder / "dev-docs.yaml").write_text(
        sample_config_text(description="書き換えた説明"), encoding="utf-8"
    )
    before = snapshot(sample.folder)
    # 実行
    checked = served.call_admin("check_project", path=str(sample.folder), format="json")
    converted = served.call_admin("try_convert", path=str(sample.folder), file="docs/doc-1.yaml")
    unchanged = snapshot(sample.folder) == before
    described_before = served.call("describe", cwd=str(sample.folder))
    reloaded = served.call_admin("reload", format="json")
    described_after = served.call("describe", cwd=str(sample.folder))
    status = served.call_admin("status", format="json").data
    # 検証
    assert not checked.is_error
    assert checked.data.get("violations", []) == []
    assert checked.data["sync"] == SYNC_ZERO
    assert not converted.is_error
    assert "文書 1" in converted.data["markdown"]
    assert unchanged
    assert "書き換えた説明" not in described_before.text
    assert not reloaded.is_error
    assert "書き換えた説明" in described_after.text
    assert not described_before.is_error
    assert status["pid"] == pid


def test_normal_when_config_version_old(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """設定のバージョンが古い配信元は、古い設定として返す（正常系）。"""
    # 準備
    config = sample_config_text(name="old", version="0")
    old = make_source("old", sample_file_set(**{"dev-docs.yaml": config}))
    served = serve(old)
    # 実行
    checked = served.call_admin("check_project", path=str(old.folder), format="json")
    # 検証
    assert not checked.is_error
    assert checked.data["config_version"] == "0"
    assert checked.data["version_state"] == "old"
    assert checked.data.get("violations", []) == []


def test_error_when_config_invalid(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """変えた設定が検証に通らないと違反を返し、`reload` までは変える前の設定で配信する（異常系）。"""
    # 準備
    sample = make_source("sample")
    served = serve(sample)
    (sample.folder / "dev-docs.yaml").write_text(BROKEN_CONFIG, encoding="utf-8")
    # 実行
    checked = served.call_admin("check_project", path=str(sample.folder), format="json")
    searched = served.call(
        "search_docs", cwd=str(sample.folder), source="sample", view="ids", format="json"
    )
    # 検証
    violations = checked.data["violations"]
    assert [item["path"] for item in violations] == ["documents[0].paths"]
    assert violations[0]["rule"]
    assert not searched.is_error
    assert [item["id"] for item in searched.data["items"]] == ["doc-1", "doc-2"]


def test_error_when_converter_fails(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    snapshot: Callable[..., dict[str, bytes]],
) -> None:
    """変換スクリプトが失敗すると、終了コードと標準エラーを返し、配信は変えない（異常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(CONVERTER_EXTRA),
            "scripts/convert.py": CONVERT_OK,
        }
    )
    sample = make_source("sample", files)
    served = serve(sample)
    (sample.folder / "scripts" / "convert.py").write_text(CONVERT_FAILING, encoding="utf-8")
    before = snapshot(sample.folder)
    # 実行
    converted = served.call_admin("try_convert", path=str(sample.folder), file="docs/doc-1.yaml")
    status = served.call_admin("status", format="json").data
    # 検証
    assert converted.is_error
    assert "3" in converted.text
    assert "変換に失敗した" in converted.text
    assert snapshot(sample.folder) == before
    assert [source["id"] for source in status["sources"] if source["status"] == "serving"] == [
        "sample"
    ]
