"""公開の文書と判定フローチャートを、mdmark の build で GitHub Pages の 1 枚の HTML にまとめる。

docs/guide/files.yml の visibility: public の Markdown と、docs/flowchart/ の visibility: public の
YAML を Markdown にしたものを、分類（はじめに・使い方・リファレンス）の順に並べてまとめる。
GitHub Actions の Pages のワークフローと、手元の確認から、リポジトリの直下で起動する。

Usage:
# 公開ページを tmp/pages/index.html に作る（tmp/pages は中身を削除してから作る）
uv run --frozen python scripts/build_pages.py --out tmp/pages
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# 文書の ID を集めるフォルダ
DOCS_DIR = "docs"

# 公開の Markdown を配置するフォルダと、その公開範囲・分類を持つファイル名
GUIDE_DIR = "docs/guide"
GUIDE_FILES = "files.yml"

# 変換する YAML を配置するフォルダ
FLOWCHART_DIR = "docs/flowchart"

# 公開ページの文書の一覧に並べる分類の順と、判定フローチャートを並べる分類
CATEGORIES = ("はじめに", "使い方", "リファレンス")
FLOWCHART_CATEGORY = "使い方"

# 文書の原本でないため ID を集めない docs/ 直下のフォルダと、目次・管理用の YAML のファイル名
SKIPPED_DIRS = ("pr", "mock", "generated")
SKIPPED_FILES = ("index.yaml", "files.yml")

# 公開ページにまとめない文書への参照のリンクの頭
BLOB_URL = "https://github.com/shuhei1101/dev-docs/blob/develop/"

# 公開ページにまとめる visibility の値
PUBLIC = "public"

# 見出しを付けずに冒頭リードにする項目の id
OVERVIEW_ID = "overview"

# 項目の group を入れ子の見出しに分ける区切り
GROUP_SEPARATOR = " > "

# group を持たない項目と、group の 1 つ目のレイヤーの見出しの深さと、見出しの最大の深さ
ITEM_HEADING_LEVEL = 2
MAX_HEADING_LEVEL = 6

# npx で呼ぶ mdmark のタグ（画面が参照する mdmark の採用バージョンと同じ）
MDMARK_TAG = "v0.10.0"

# 出力のフォルダに配置する、Pages のトップになる HTML
OUTPUT_HTML = "index.html"

# mdmark の build を打ち切る秒数（初回の npx の取得を含む）
LIMIT_SEC = 300

# 終了コード。1 = 作れない・想定していない例外、2 = 公開の文書が無く作り始めなかった
EXIT_FAILED = 1
EXIT_NOT_STARTED = 2

# 一時フォルダに記載する mdmark の設定のファイル名
_BUNDLE_CONFIG = "mdmark.config.yaml"

# ATX の見出しの行とコードブロックの囲み
_ATX_HEADING = re.compile(r"^(#{1,6})(?:\s+(.*?))?\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")

# 見出しの ID から除く文字（文字・数字・_・-・空白のほか）
_SLUG_REMOVE = re.compile(r"[^\w\- ]")

# 文書への参照（](id:{対象}) と ](id:{対象}#{項目})）
_REFERENCE = re.compile(r"\]\(id:([^)#\s]+)(?:#([^)\s]+))?\)")


@dataclass(frozen=True)
class GuidePage:
    """docs/guide/files.yml の公開の行 1 つ。"""

    # docs/guide/ からのファイル名
    path: str
    # 分類（CATEGORIES のどれか）
    category: str


class BuildError(Exception):
    """入力の誤り・mdmark の build の失敗で公開ページを作れない。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _load_yaml(text: str) -> Any:
    """YAML の文字列を safe の方式で読み込む。"""
    return YAML(typ="safe", pure=True).load(text)


def main(argv: Sequence[str] | None = None) -> int:
    """公開の文書を 1 枚の HTML にして出力のフォルダに配置し、終了コードを返却する。"""
    parser = argparse.ArgumentParser(
        description="公開の文書を mdmark の build で 1 枚の HTML にまとめる"
    )
    parser.add_argument("--root", type=Path, default=Path(), help="リポジトリの直下")
    parser.add_argument(
        "--out", required=True, type=Path, help="出力のフォルダ（中身を削除して再作成する）"
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    out: Path = args.out

    try:
        # 公開の文書を集める
        guides = list_public_guides(root)
        flowcharts = load_public_flowcharts(root)
        # 公開の文書が無い: 出力のフォルダを触らずに終わる
        if not guides and not flowcharts:
            print("visibility: public の文書がありません", file=sys.stderr)
            return EXIT_NOT_STARTED
        paths = index_document_paths(root)

        # 判定フローチャートは全てを描いて見出しの ID を統一してから、参照を書き換える
        markdowns = {str(doc["id"]): render_page(doc) for doc in flowcharts}
        anchors = {
            str(doc["id"]): item_anchors(markdowns[str(doc["id"])], doc) for doc in flowcharts
        }
        public_ids = {f"{GUIDE_DIR}/{page.path}": page.path for page in guides}
        public_ids.update({doc_id: f"{doc_id}.md" for doc_id in markdowns})

        # 出力のフォルダは再作成し、失敗したときは空のまま残す
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)

        with tempfile.TemporaryDirectory() as temp:
            workdir = Path(temp)
            names: list[str] = []
            # 分類の順に、公開ドキュメントの文書と（使い方なら）判定フローチャートを並べる
            for category in CATEGORIES:
                for page in guides:
                    if page.category == category:
                        shutil.copyfile(root / GUIDE_DIR / page.path, workdir / page.path)
                        names.append(page.path)
                if category != FLOWCHART_CATEGORY:
                    continue
                for doc_id, markdown in markdowns.items():
                    text = rewrite_references(
                        markdown, public_ids=public_ids, anchors=anchors, paths=paths, root=root
                    )
                    (workdir / f"{doc_id}.md").write_text(text, encoding="utf-8")
                    names.append(f"{doc_id}.md")

            # mdmark の build で 1 枚にまとめ、出力のフォルダへ移す
            config = write_bundle_config(workdir, names)
            print(run_mdmark(config).rstrip("\n"))
            shutil.copyfile(workdir / OUTPUT_HTML, out / OUTPUT_HTML)
    except BuildError as error:
        print(error.message, file=sys.stderr)
        return EXIT_FAILED
    except Exception:  # noqa: BLE001 - 想定していない例外は traceback を出して終了コードで返却する
        traceback.print_exc()
        return EXIT_FAILED
    return 0


def list_public_guides(root: Path) -> list[GuidePage]:
    """docs/guide/files.yml の行のうち visibility が public の文書を、行の順に返却する。"""
    files_yml = root / GUIDE_DIR / GUIDE_FILES
    # 管理用の YAML が無い: 公開ドキュメントの文書は無い
    if not files_yml.is_file():
        return []
    try:
        data = _load_yaml(files_yml.read_text(encoding="utf-8"))
    except YAMLError as error:
        message = f"{GUIDE_DIR}/{GUIDE_FILES}: YAML として読み込めません"
        raise BuildError(message) from error
    rows = data.get("files") if isinstance(data, dict) else None
    pages: list[GuidePage] = []
    for row in rows if isinstance(rows, list) else []:
        # public でない行は公開ページにまとめない
        if not isinstance(row, dict) or row.get("visibility") != PUBLIC:
            continue
        path = str(row.get("path"))
        category = row.get("category")
        # 分類が並びに無い: 文書の一覧のどこに並べるか決まらない
        if category not in CATEGORIES:
            message = f"{GUIDE_DIR}/{path}: 分類が {'・'.join(CATEGORIES)} のどれでもありません"
            raise BuildError(message)
        # ファイルが無い: 管理用の YAML と実体が食い違っている
        if not (root / GUIDE_DIR / path).is_file():
            message = f"{GUIDE_DIR}/{path}: ファイルがありません"
            raise BuildError(message)
        pages.append(GuidePage(path=path, category=str(category)))
    return pages


def load_public_flowcharts(root: Path) -> list[dict[str, Any]]:
    """docs/flowchart/ の直下の YAML のうち visibility が public の文書を、ファイル名の順に返却する。"""
    folder = root / FLOWCHART_DIR
    # フォルダが無い: 判定フローチャートは無い
    if not folder.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for file in sorted(folder.glob("*.yaml")):
        if file.name in SKIPPED_FILES:
            continue
        relative = f"{FLOWCHART_DIR}/{file.name}"
        try:
            doc = _load_yaml(file.read_text(encoding="utf-8"))
        except YAMLError as error:
            message = f"{relative}: YAML として読み込めません"
            raise BuildError(message) from error
        if not isinstance(doc, dict):
            message = f"{relative}: トップレベルがマッピングではありません"
            raise BuildError(message)
        if not isinstance(doc.get("id"), str) or not isinstance(doc.get("name"), str):
            message = f"{relative}: id と name が文字列ではありません"
            raise BuildError(message)
        if doc.get("visibility") == PUBLIC:
            docs.append(doc)
    return docs


def index_document_paths(root: Path) -> dict[str, str]:
    """docs/ の配下の YAML の文書のトップレベルの id から、ID → リポジトリの直下からのパスを作る。"""
    paths: dict[str, str] = {}
    docs_root = root / DOCS_DIR
    for file in sorted(docs_root.rglob("*.yaml")):
        relative = file.relative_to(docs_root)
        # 文書の原本でないフォルダと、目次・管理用の YAML は飛ばす
        if relative.parts[0] in SKIPPED_DIRS or file.name in SKIPPED_FILES:
            continue
        try:
            doc = _load_yaml(file.read_text(encoding="utf-8"))
        except YAMLError:
            # 変換する文書は公開の判定フローチャートの読み込みが確認するため、ここでは飛ばす
            continue
        if isinstance(doc, dict) and isinstance(doc.get("id"), str):
            paths.setdefault(doc["id"], f"{DOCS_DIR}/{relative.as_posix()}")
    return paths


def _heading(level: int, text: str) -> str:
    """深さを MAX_HEADING_LEVEL で抑えた ATX の見出しを作る。"""
    return f"{'#' * min(level, MAX_HEADING_LEVEL)} {text}"


def render_page(document: Mapping[str, Any]) -> str:
    """判定フローチャートの文書 1 つを、# {name} と項目の見出し・本文の Markdown にする。"""
    blocks = [_heading(1, str(document["name"]))]
    current: list[str] = []
    for item in document.get("items") or []:
        if not isinstance(item, dict):
            continue
        body = str(item.get("body") or "")
        # 概要: 見出しを付けずに冒頭リードにする
        if item.get("id") == OVERVIEW_ID:
            blocks.append(body)
            continue
        group = item.get("group")
        levels = group.split(GROUP_SEPARATOR) if isinstance(group, str) and group.strip() else []
        # 直前の項目とレイヤーが違うところから、group の見出しを配置する
        common = 0
        while common < min(len(levels), len(current)) and levels[common] == current[common]:
            common += 1
        blocks += [
            _heading(ITEM_HEADING_LEVEL + depth, levels[depth])
            for depth in range(common, len(levels))
        ]
        current = levels
        blocks.append(_heading(ITEM_HEADING_LEVEL + len(levels), str(item.get("name"))))
        blocks.append(body)
    return "\n\n".join(block for block in blocks if block) + "\n"


def _github_slug(text: str) -> str:
    """見出しの文字から、mdmark と同じ GitHub の規則の ID を作る。"""
    return _SLUG_REMOVE.sub("", text.strip().lower()).replace(" ", "-")


def item_anchors(markdown: str, document: Mapping[str, Any]) -> dict[str, str]:
    """描いた Markdown の見出しを文書の項目と突き合わせ、項目の id → 見出しの ID を返却する。"""
    # コードブロックの外の見出しを、（深さ、文字、ID）で上から並べる
    headings: list[tuple[int, str, str]] = []
    counts: dict[str, int] = {}
    fence: str | None = None
    for line in markdown.splitlines():
        opened = _FENCE.match(line)
        if opened is not None:
            # 開いた囲みと同じ記号で閉じる
            if fence is None:
                fence = opened.group(1)
            elif opened.group(1) == fence:
                fence = None
            continue
        matched = _ATX_HEADING.match(line) if fence is None else None
        if matched is None:
            continue
        text = matched.group(2) or ""
        slug = _github_slug(text)
        # 同じ ID の 2 つ目からは -1・-2 を付ける
        if slug in counts:
            counts[slug] += 1
            slug = f"{slug}-{counts[slug]}"
        else:
            counts[slug] = 0
        headings.append((len(matched.group(1)), text, slug))

    # 項目を順に、直前に対応づけた見出しより後の、同じ深さと文字の最初の見出しに対応づける
    anchors: dict[str, str] = {}
    start = 0
    for item in document.get("items") or []:
        if not isinstance(item, dict) or item.get("id") == OVERVIEW_ID:
            continue
        group = item.get("group")
        levels = group.split(GROUP_SEPARATOR) if isinstance(group, str) and group.strip() else []
        depth = min(ITEM_HEADING_LEVEL + len(levels), MAX_HEADING_LEVEL)
        for position in range(start, len(headings)):
            level, text, slug = headings[position]
            if level == depth and text == item.get("name"):
                anchors[str(item.get("id"))] = slug
                start = position + 1
                break
    return anchors


def rewrite_references(
    text: str,
    *,
    public_ids: Mapping[str, str],
    anchors: Mapping[str, Mapping[str, str]],
    paths: Mapping[str, str],
    root: Path,
) -> str:
    """本文の文書への参照を、まとめた中のリンクか GitHub の URL に書き換える。"""

    def _replace(matched: re.Match[str]) -> str:
        target, item = matched.group(1), matched.group(2)
        name = public_ids.get(target)
        # まとめる文書: 1 枚の中のリンク。項目の見出しがあればその見出しへ
        if name is not None:
            anchor = anchors.get(target, {}).get(item) if item is not None else None
            return f"](./{name}#{anchor})" if anchor is not None else f"](./{name})"
        # まとめない文書: 文書の ID か docs/ の実在するパスなら develop の URL（項目は落とす）
        path = paths.get(target)
        if path is None and target.startswith(f"{DOCS_DIR}/") and (root / target).is_file():
            path = target
        if path is None:
            message = f"参照を解決できません: id:{target}"
            raise BuildError(message)
        encoded = "/".join(quote(part) for part in PurePosixPath(path).parts)
        return f"]({BLOB_URL}{encoded})"

    lines: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        opened = _FENCE.match(line)
        # コードブロックの囲みの行と中の行は書き換えない
        if opened is not None:
            if fence is None:
                fence = opened.group(1)
            elif opened.group(1) == fence:
                fence = None
            lines.append(line)
            continue
        lines.append(line if fence is not None else _REFERENCE.sub(_replace, line))
    return "\n".join(lines)


def write_bundle_config(workdir: Path, names: Sequence[str]) -> Path:
    """一時フォルダに、まとめる文書を並びのとおりまとめる mdmark の設定を記載する。"""
    config = {
        "version": MDMARK_TAG,
        "build": {"include": list(names), "entry": names[0], "out": OUTPUT_HTML},
    }
    path = workdir / _BUNDLE_CONFIG
    # JSON は YAML として読み込める
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_mdmark(config: Path) -> str:
    """npx で mdmark の build を実行し、標準出力を返却する。"""
    try:
        result = subprocess.run(
            [
                "npx",
                "-y",
                f"github:shuhei1101/mdmark#{MDMARK_TAG}",
                "build",
                "--config",
                str(config),
            ],
            cwd=config.parent,
            capture_output=True,
            encoding="utf-8",
            timeout=LIMIT_SEC,
            check=False,
        )
    except FileNotFoundError as error:
        message = "npx が PATH にありません。Node 24 以降を入れてください"
        raise BuildError(message) from error
    except subprocess.TimeoutExpired as error:
        message = f"mdmark の build が {LIMIT_SEC} 秒で終わりませんでした"
        raise BuildError(message) from error
    # 終了コードが 0 でない: 標準エラーを添えて止める
    if result.returncode != 0:
        message = (
            f"mdmark の build が終了コード {result.returncode} で失敗しました\n{result.stderr}"
        )
        raise BuildError(message)
    # mdmark の警告はそのまま標準エラーへ出す
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.stdout


if __name__ == "__main__":
    sys.exit(main())
