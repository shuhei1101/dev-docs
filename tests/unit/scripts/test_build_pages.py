from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _write(path: Path, text: str) -> None:
    """親のフォルダを作って UTF-8 で書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _guide_files(root: Path, rows: list[dict[str, str]]) -> None:
    """`docs/guide/files.yml` を JSON（YAML として読める）で書く。"""
    _write(root / "docs/guide/files.yml", json.dumps({"files": rows}, ensure_ascii=False))


def _flowchart(root: Path, name: str, doc: dict[str, Any]) -> None:
    """`docs/flowchart/{name}` に判定フローチャートを JSON（YAML として読める）で書く。"""
    _write(root / "docs/flowchart" / name, json.dumps(doc, ensure_ascii=False))


def _doc(doc_id: str, visibility: str, items: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """判定フローチャートの文書の中身を作る。"""
    return {
        "id": doc_id,
        "name": f"{doc_id} 判定フローチャート",
        "visibility": visibility,
        "items": items if items is not None else [{"id": "overview", "name": "概要", "body": "概要の本文"}],
    }


# --- main ---


def test_main(
    build_pages: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """公開の文書を分類の順に並べて mdmark に渡し、`OUTPUT_HTML` を `--out` に置く。"""
    root = tmp_path / "repo"
    _guide_files(
        root,
        [
            {"path": "use.md", "visibility": "public", "category": "使い方"},
            {"path": "secret.md", "visibility": "internal", "category": "使い方"},
            {"path": "intro.md", "visibility": "public", "category": "はじめに"},
        ],
    )
    for name in ("use.md", "secret.md", "intro.md"):
        _write(root / "docs/guide" / name, f"# {name}\n")
    _flowchart(root, "flowchart-a.yaml", _doc("flowchart-a", "public"))
    recorded: dict[str, Any] = {}

    def _fake_run(config: Path) -> str:
        recorded.update(json.loads(config.read_text(encoding="utf-8")))
        recorded["files"] = sorted(p.name for p in config.parent.iterdir())
        (config.parent / build_pages.OUTPUT_HTML).write_text("<html></html>", encoding="utf-8")
        return "built\n"

    monkeypatch.setattr(build_pages, "run_mdmark", _fake_run)
    out = tmp_path / "site"

    code = build_pages.main(["--root", str(root), "--out", str(out)])

    assert code == 0
    assert (out / build_pages.OUTPUT_HTML).read_text(encoding="utf-8") == "<html></html>"
    assert recorded["build"]["include"] == ["intro.md", "use.md", "flowchart-a.md"]
    assert "secret.md" not in recorded["files"]


def test_main_when_no_public(
    build_pages: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """公開の文書が無ければ `EXIT_NOT_STARTED` を返し、`--out` を作らない。"""
    root = tmp_path / "repo"
    _guide_files(root, [{"path": "secret.md", "visibility": "internal", "category": "使い方"}])
    _write(root / "docs/guide/secret.md", "# secret\n")
    _flowchart(root, "flowchart-a.yaml", _doc("flowchart-a", "internal"))

    def _never(config: Path) -> str:
        raise AssertionError(config)

    monkeypatch.setattr(build_pages, "run_mdmark", _never)
    out = tmp_path / "site"

    code = build_pages.main(["--root", str(root), "--out", str(out)])

    assert code == build_pages.EXIT_NOT_STARTED
    assert not out.exists()


def test_main_when_build_failed(
    build_pages: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """mdmark の build が失敗すれば `EXIT_FAILED` を返し、標準エラーにメッセージを出す。"""
    root = tmp_path / "repo"
    _guide_files(root, [{"path": "intro.md", "visibility": "public", "category": "はじめに"}])
    _write(root / "docs/guide/intro.md", "# intro\n")

    def _fail(config: Path) -> str:
        raise build_pages.BuildError("mdmark の build が失敗しました")

    monkeypatch.setattr(build_pages, "run_mdmark", _fail)

    code = build_pages.main(["--root", str(root), "--out", str(tmp_path / "site")])

    assert code == build_pages.EXIT_FAILED
    assert "mdmark の build が失敗しました" in capsys.readouterr().err


# --- list_public_guides ---


def test_list_public_guides(build_pages: ModuleType, tmp_path: Path) -> None:
    """public の行だけを行の順に返す。"""
    _guide_files(
        tmp_path,
        [
            {"path": "use.md", "visibility": "public", "category": "使い方"},
            {"path": "secret.md", "visibility": "internal", "category": "使い方"},
            {"path": "intro.md", "visibility": "public", "category": "はじめに"},
        ],
    )
    for name in ("use.md", "secret.md", "intro.md"):
        _write(tmp_path / "docs/guide" / name, "x")

    pages = build_pages.list_public_guides(tmp_path)

    assert [(p.path, p.category) for p in pages] == [("use.md", "使い方"), ("intro.md", "はじめに")]


def test_list_public_guides_when_no_file(build_pages: ModuleType, tmp_path: Path) -> None:
    """管理用の YAML が無ければ空のリストを返す。"""
    assert build_pages.list_public_guides(tmp_path) == []


@pytest.mark.parametrize(
    ("row", "create"),
    [
        pytest.param({"path": "a.md", "visibility": "public"}, True, id="no_category"),
        pytest.param({"path": "a.md", "visibility": "public", "category": "使い方"}, False, id="no_file"),
    ],
)
def test_list_public_guides_when_invalid_row(
    build_pages: ModuleType, tmp_path: Path, row: dict[str, str], create: bool
) -> None:
    """分類かファイルが無い public の行は `BuildError` にする。"""
    _guide_files(tmp_path, [row])
    if create:
        _write(tmp_path / "docs/guide/a.md", "x")

    with pytest.raises(build_pages.BuildError, match="a.md"):
        build_pages.list_public_guides(tmp_path)


# --- load_public_flowcharts ---


def test_load_public_flowcharts(build_pages: ModuleType, tmp_path: Path) -> None:
    """public だけをファイル名の順に返す。"""
    _flowchart(tmp_path, "b.yaml", _doc("b", "public"))
    _flowchart(tmp_path, "a.yaml", _doc("a", "public"))
    _flowchart(tmp_path, "c.yaml", _doc("c", "internal"))
    _write(tmp_path / "docs/flowchart/index.yaml", "summary: x\nitems: []\n")

    docs = build_pages.load_public_flowcharts(tmp_path)

    assert [d["id"] for d in docs] == ["a", "b"]


def test_load_public_flowcharts_when_no_folder(build_pages: ModuleType, tmp_path: Path) -> None:
    """フォルダが無ければ空のリストを返す。"""
    assert build_pages.load_public_flowcharts(tmp_path) == []


def test_load_public_flowcharts_when_invalid(build_pages: ModuleType, tmp_path: Path) -> None:
    """読み込めない YAML はパスを添えて `BuildError` にする。"""
    _write(tmp_path / "docs/flowchart/broken.yaml", "{")

    with pytest.raises(build_pages.BuildError, match="broken.yaml"):
        build_pages.load_public_flowcharts(tmp_path)


# --- index_document_paths ---


def test_index_document_paths(build_pages: ModuleType, tmp_path: Path) -> None:
    """文書の ID だけを集める。"""
    _write(tmp_path / "docs/module/MOD-1.py.yaml", "id: MOD-1\n")
    _write(tmp_path / "docs/pr/1/x.yaml", "id: X\n")
    _write(tmp_path / "docs/flowchart/index.yaml", "id: INDEX\n")
    _write(tmp_path / "docs/module/broken.yaml", "{")

    assert build_pages.index_document_paths(tmp_path) == {"MOD-1": "docs/module/MOD-1.py.yaml"}


# --- render_page ---


def test_render_page(build_pages: ModuleType) -> None:
    """概要は見出し無し、group は 1 つの見出しの下に項目、group 無しは 2 の深さで描く。"""
    doc = {
        "id": "f",
        "name": "判定",
        "items": [
            {"id": "overview", "name": "概要", "body": "概要の本文"},
            {"id": "a", "group": "G", "name": "A", "body": "A の本文"},
            {"id": "b", "group": "G", "name": "B", "body": "B の本文"},
            {"id": "c", "name": "C", "body": "C の本文"},
        ],
    }

    markdown = build_pages.render_page(doc)

    assert markdown == (
        "# 判定\n\n概要の本文\n\n## G\n\n### A\n\nA の本文\n\n### B\n\nB の本文\n\n## C\n\nC の本文\n"
    )


def test_render_page_when_nested_group(build_pages: ModuleType) -> None:
    """group の入れ子はレイヤーごとに見出しを置き、共通のレイヤーは繰り返さない。"""
    doc = {
        "id": "f",
        "name": "判定",
        "items": [
            {"id": "x", "group": "A > B", "name": "X", "body": "x"},
            {"id": "y", "group": "A > C", "name": "Y", "body": "y"},
        ],
    }

    markdown = build_pages.render_page(doc)

    assert markdown == "# 判定\n\n## A\n\n### B\n\n#### X\n\nx\n\n### C\n\n#### Y\n\ny\n"


# --- item_anchors ---


def test_item_anchors(build_pages: ModuleType) -> None:
    """項目を見出しに対応づけ、2 つ目の同じ ID には `-1` を付ける。"""
    doc = {
        "items": [
            {"id": "overview", "name": "概要", "body": ""},
            {"id": "flow", "group": "判定 Flow", "name": "判定 Flow", "body": ""},
        ]
    }
    markdown = "# 判定\n\n## 判定 Flow\n\n### 判定 Flow\n\nx\n"

    assert build_pages.item_anchors(markdown, doc) == {"flow": "判定-flow-1"}


def test_item_anchors_when_in_code_block(build_pages: ModuleType) -> None:
    """コードブロックの中の行は見出しにしない。"""
    doc = {"items": [{"id": "x", "name": "x", "body": ""}]}
    markdown = "# t\n\n```text\n## x\n```\n\n## x\n"

    assert build_pages.item_anchors(markdown, doc) == {"x": "x"}


# --- rewrite_references ---


def _rewrite(build_pages: ModuleType, text: str, **kwargs: Any) -> str:
    """既定の空の対応で `rewrite_references` を呼ぶ。"""
    options: dict[str, Any] = {"public_ids": {}, "anchors": {}, "paths": {}, "root": Path("/nonexistent")}
    options.update(kwargs)
    result: str = build_pages.rewrite_references(text, **options)
    return result


def test_rewrite_references(build_pages: ModuleType) -> None:
    """公開の判定フローチャートは 1 枚の中のリンクにし、項目は見出しの ID にする。"""
    text = "[x](id:flowchart-a) と [y](id:flowchart-a#q1)"

    result = _rewrite(
        build_pages,
        text,
        public_ids={"flowchart-a": "flowchart-a.md"},
        anchors={"flowchart-a": {"q1": "判定"}},
    )

    assert result == "[x](./flowchart-a.md) と [y](./flowchart-a.md#判定)"


def test_rewrite_references_when_guide_path(build_pages: ModuleType) -> None:
    """公開ドキュメントのパスは 1 枚の中のリンクにする。"""
    result = _rewrite(
        build_pages, "[設定](id:docs/guide/設定.md)", public_ids={"docs/guide/設定.md": "設定.md"}
    )

    assert result == "[設定](./設定.md)"


def test_rewrite_references_when_internal_document(build_pages: ModuleType) -> None:
    """まとめない文書は develop の GitHub の URL にし、項目を落とす。"""
    result = _rewrite(
        build_pages, "[m](id:MOD-1#functions[main])", paths={"MOD-1": "docs/module/MOD-1.py.yaml"}
    )

    assert result == "[m](https://github.com/shuhei1101/dev-docs/blob/develop/docs/module/MOD-1.py.yaml)"


def test_rewrite_references_when_in_code_block(build_pages: ModuleType) -> None:
    """コードブロックの中は書き換えない。"""
    text = "```text\n[x](id:flowchart-a)\n```"

    assert _rewrite(build_pages, text, public_ids={"flowchart-a": "flowchart-a.md"}) == text


def test_rewrite_references_when_unresolved(build_pages: ModuleType) -> None:
    """解決できない参照は `BuildError` にする。"""
    with pytest.raises(build_pages.BuildError, match="id:NOPE-1"):
        _rewrite(build_pages, "[z](id:NOPE-1)")


# --- write_bundle_config ---


def test_write_bundle_config(build_pages: ModuleType, tmp_path: Path) -> None:
    """並びのとおりの mdmark の設定を書く。"""
    config = build_pages.write_bundle_config(tmp_path, ["a.md", "b.md"])

    assert json.loads(config.read_text(encoding="utf-8")) == {
        "version": build_pages.MDMARK_TAG,
        "build": {"include": ["a.md", "b.md"], "entry": "a.md", "out": build_pages.OUTPUT_HTML},
    }


# --- run_mdmark ---


def test_run_mdmark(
    build_pages: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`npx` で mdmark の build を設定のフォルダで実行し、標準出力を返す。"""
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def _fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="built\n", stderr="")

    monkeypatch.setattr(build_pages.subprocess, "run", _fake)
    config = tmp_path / "mdmark.config.yaml"

    assert build_pages.run_mdmark(config) == "built\n"
    args, kwargs = calls[0]
    assert args == [
        "npx",
        "-y",
        f"github:shuhei1101/mdmark#{build_pages.MDMARK_TAG}",
        "build",
        "--config",
        str(config),
    ]
    assert kwargs["cwd"] == tmp_path


def test_run_mdmark_when_failed(
    build_pages: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """終了コードが 0 でなければ、終了コードと標準エラーを添えて `BuildError` にする。"""

    def _fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="broken")

    monkeypatch.setattr(build_pages.subprocess, "run", _fake)

    with pytest.raises(build_pages.BuildError, match=r"終了コード 1(.|\n)*broken"):
        build_pages.run_mdmark(tmp_path / "mdmark.config.yaml")


def test_run_mdmark_when_npx_missing(
    build_pages: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`npx` が無ければ Node を入れる案内を添えて `BuildError` にする。"""

    def _fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(build_pages.subprocess, "run", _fake)

    with pytest.raises(build_pages.BuildError, match="Node"):
        build_pages.run_mdmark(tmp_path / "mdmark.config.yaml")
