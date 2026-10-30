from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
NAV = (
    "nav:\n"
    "  tabs:\n"
    "    - title: 規約\n"
    "      items:\n"
    "        - auto:\n"
    "            document: sample\n"
    "    - title: 補足\n"
    "      items:\n"
    "        - page: sample/doc-2\n"
)
TABLE_DOC = (
    "id: doc-1\n"
    "name: 文書 1\n"
    "items:\n"
    "  - {key: k1, label: 名称 1, notes: 備考 1}\n"
    "  - {key: k2, label: 名称 2, notes: 備考 2}\n"
)
CONVERT_SCRIPT = (
    "import sys\n"
    "text = sys.stdin.read()\n"
    "name = next(line.split(':', 1)[1].strip() for line in text.splitlines()"
    " if line.startswith('name:'))\n"
    "print(f'# カスタム変換: {name}')\n"
)
SLEEP_SCRIPT = "import os, time\nopen('pid.txt', 'w').write(str(os.getpid()))\ntime.sleep(60)\n"
CUSTOM_EXTRA = (
    "  - id: custom\n"
    "    paths: [custom/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    converter: md\n"
    "  - id: guide\n"
    "    paths: [guide/files.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
    "converters:\n"
    "  - id: md\n"
    "    run: [python3, scripts/convert.py]\n"
)


def _page_changes(items: list[dict[str, Any]]) -> dict[str, str | None]:
    """サイドバーの項目の入れ子をたどり、page の文書のパスと変化を対応させる。"""
    changes: dict[str, str | None] = {}
    for item in items:
        if item["kind"] == "page":
            changes[item["path"]] = item["change"]
        changes.update(_page_changes(item["items"]))
    return changes


def _custom_files(
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    script: str,
) -> dict[str, str]:
    """`converters[]` のスクリプトと埋め込みのマーカーを持つ配信元のファイル一式を返す。"""
    return sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(CUSTOM_EXTRA, name="custom"),
            "scripts/convert.py": script,
            "custom/c-1.yaml": "id: c-1\nname: カスタム 1\n",
            "guide/files.yaml": "files:\n  - path: intro.md\n",
            "guide/intro.md": "# 案内\n\n<!-- embed: data/rows.yaml#rows -->\n",
            "data/rows.yaml": "rows:\n  - {colA: 値A, colB: 値B}\n",
        }
    )


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """一番左のタブの一番上の文書と、文書のパスで指した文書を返す（正常系）。"""
    # 準備
    files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(NAV), "docs/doc-1.yaml": TABLE_DOC}
    )
    env = make_server(make_source("sample", files, date="2026-10-26T14:40:00+09:00"))
    # 実行
    top = env.client.get("/_api/sources/sample/docs")
    second = env.client.get("/_api/sources/sample/docs/docs/doc-2")
    # 検証
    body = top.json()
    assert top.status_code == 200
    assert body["path"] == "docs/doc-1"
    assert [tab["title"] for tab in body["tabs"]] == ["規約", "補足"]
    assert [tab["active"] for tab in body["tabs"]] == [True, False]
    assert "## 項目" in body["markdown"]
    assert "| キー | 名称 | 備考 |" in body["markdown"]
    assert "dev-docs-table" not in body["markdown"]
    assert len(body["tableKeys"]) == 1
    assert body["conversionError"] is None
    assert body["diff"] is None
    assert set(_page_changes(body["tabs"][0]["items"]).values()) == {None}
    assert datetime.fromisoformat(body["updatedAt"]) == datetime.fromisoformat(
        "2026-10-26T14:40:00+09:00"
    )
    assert second.status_code == 200
    assert "# 文書 2" in second.json()["markdown"]


def test_normal_when_nav_missing(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """nav が無い配信元は種類ごとにタブを作る（正常系）。"""
    # 準備
    memo = (
        "  - id: memo\n"
        "    title: メモ\n"
        "    paths: [notes/*.yaml]\n"
        "    schema: schemas/sample.schema.yaml\n"
    )
    files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(memo), "notes/n-1.yaml": "id: n-1\nname: メモ 1\n"}
    )
    env = make_server(make_source("plain", files))
    # 実行
    response = env.client.get("/_api/sources/plain/docs")
    # 検証
    tabs = response.json()["tabs"]
    assert response.status_code == 200
    assert [tab["title"] for tab in tabs] == ["sample", "メモ"]
    assert [item["path"] for item in tabs[0]["items"]] == ["docs/doc-1", "docs/doc-2"]
    assert [item["path"] for item in tabs[1]["items"]] == ["notes/n-1"]


def test_normal_when_ref_given(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
) -> None:
    """ref のリビジョンの文書を返す（正常系）。"""
    # 準備
    source = make_source("sample")
    old = run_git(source.folder, "rev-parse", "HEAD").strip()
    commit_all(source.folder, {"docs/doc-1.yaml": "id: doc-1\nname: 新しい名前\n"})
    env = make_server(source)
    # 実行
    at_old = env.client.get("/_api/sources/sample/docs/docs/doc-1", params={"ref": old})
    at_default = env.client.get("/_api/sources/sample/docs/docs/doc-1")
    # 検証
    assert at_old.status_code == 200
    assert "# 文書 1" in at_old.json()["markdown"]
    assert at_old.json()["ref"] == old
    assert "# 新しい名前" in at_default.json()["markdown"]
    assert at_default.json()["ref"] == "develop"


def test_normal_when_diff_given(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """diff のリビジョンから変わった項目と、サイドバーの page ごとの変化を返す（正常系）。"""
    # 準備
    files = sample_file_set(**{"docs/doc-3.yaml": sample_doc_text("doc-3", "文書 3")})
    source = make_source("sample", files)
    parent = run_git(source.folder, "rev-parse", "HEAD").strip()
    renamed = sample_doc_text("doc-1", "新しい名前", description="1 件目", tags=["a"])
    changed = commit_all(
        source.folder,
        {"docs/doc-1.yaml": renamed, "docs/doc-4.yaml": sample_doc_text("doc-4", "文書 4")},
        delete=("docs/doc-3.yaml",),
    )
    env = make_server(source)
    # 実行
    response = env.client.get(
        "/_api/sources/sample/docs/docs/doc-1", params={"ref": changed, "diff": parent}
    )
    # 検証
    body = response.json()
    assert response.status_code == 200
    assert body["diff"] == {"base": parent, "change": "modified", "changedItems": ["name"]}
    assert "# 新しい名前" in body["markdown"]
    assert _page_changes(body["tabs"][0]["items"]) == {
        "docs/doc-1": "modified",
        "docs/doc-2": None,
        "docs/doc-3": "deleted",
        "docs/doc-4": "added",
    }


def test_normal_when_custom_converter(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """converters[] のスクリプトの Markdown と、埋め込みのマーカーの表を返す（正常系）。"""
    # 準備
    files = _custom_files(sample_file_set, sample_config_text, CONVERT_SCRIPT)
    env = make_server(make_source("custom", files))
    # 実行
    converted = env.client.get("/_api/sources/custom/docs/custom/c-1")
    embedded = env.client.get("/_api/sources/custom/docs/guide/files/guide/intro")
    # 検証
    assert converted.status_code == 200
    assert "# カスタム変換: カスタム 1" in converted.json()["markdown"]
    assert embedded.status_code == 200
    assert "| colA | colB |" in embedded.json()["markdown"]
    assert "embed:" not in embedded.json()["markdown"]


def test_normal_when_conversion_failed(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    commit_all: Callable[..., str],
) -> None:
    """制限時間を超えたスクリプトを止め、conversionError に失敗を入れる（正常系）。"""
    # 準備
    files = _custom_files(sample_file_set, sample_config_text, SLEEP_SCRIPT)
    source = make_source("custom", files)
    env = make_server(source, settings_extra="script_timeout_sec: 1\n")
    # 実行
    timed_out = env.client.get("/_api/sources/custom/docs/custom/c-1")
    schema_driven = env.client.get("/_api/sources/custom/docs/docs/doc-2")
    commit_all(source.folder, {"docs/doc-1.yaml": "a: [1\n"}, "docs: 壊す")
    unreadable = env.client.get("/_api/sources/custom/docs/docs/doc-1")
    # 検証
    error = timed_out.json()["conversionError"]
    pid = int((source.folder / "pid.txt").read_text(encoding="utf-8"))
    assert timed_out.status_code == 200
    assert timed_out.json()["markdown"] is None
    assert error["reason"] == "timeout"
    assert error["kind"] == "custom"
    assert "scripts/convert.py" in error["script"]
    assert "1" in error["detail"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert schema_driven.status_code == 200
    assert "# 文書 2" in schema_driven.json()["markdown"]
    broken = unreadable.json()["conversionError"]
    assert unreadable.status_code == 200
    assert unreadable.json()["markdown"] is None
    assert broken["reason"] == "invalid_yaml"
    assert broken["file"] == "docs/doc-1.yaml"
    assert broken["line"] >= 1
    assert broken["column"] >= 1


def test_error_when_not_found(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """無い配信元・リビジョン・文書を断り、何が無いかを返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG})
    env = make_server(sample, broken)
    # 実行
    no_doc = env.client.get("/_api/sources/sample/docs/no-such-doc")
    no_ref = env.client.get("/_api/sources/sample/docs", params={"ref": "no-such-branch"})
    not_served = env.client.get("/_api/sources/broken/docs")
    unknown = env.client.get("/_api/sources/unknown/docs")
    # 検証
    assert no_doc.status_code == 404
    assert (no_doc.json()["missing"], no_doc.json()["value"]) == ("doc", "no-such-doc")
    assert no_ref.status_code == 404
    assert (no_ref.json()["missing"], no_ref.json()["value"]) == ("ref", "no-such-branch")
    assert not_served.status_code == 404
    assert not_served.json()["missing"] == "not_served"
    assert any(error["path"] == "documents[0].paths" for error in not_served.json()["errors"])
    assert unknown.status_code == 404
    assert (unknown.json()["missing"], unknown.json()["value"]) == ("source", "unknown")
