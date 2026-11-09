"""文字列の値の本文の書き換えと、参照の値のリンクへの組み立て。"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import quote

from dev_docs.features.convert.decisions import DECISION_PAGE_PREFIX
from dev_docs.features.convert.diagrams import render_mermaid
from dev_docs.features.convert.types import DiagramHead, RenderContext

TREE_LINE = re.compile(r"^(\S.*|(│   |\|   |    )*(├── |└── |\|-- |`-- ).+)$")
TREE_BRANCH = re.compile(r"(├── |└── |\|-- |`-- )")
ISSUE_NUMBER = re.compile(r"(?<![\w/&\[(])#(\d+)\b")
CHOICE = re.compile(r"^'([^']+)'（(.+)）$")
CHOICE_SEPARATOR = " / "
TREE_MIN_LINES = 2
MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)\n```", re.S)
PLAIN_BLOCK = re.compile(r"^```\n(.*?)\n```$", re.S | re.M)
STEP_LINE = re.compile(r"^\d+\. ")
# Issue 番号・id のリンクを書き換えない、コードブロックと行内のコード
CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.S)
# 本文の `[名前](id:{文書の ID})`・`[名前](id:{文書の ID}#{項目のパス})`
ID_LINK = re.compile(r"\[(?P<name>[^\]]*)\]\(id:(?P<id>[^)#\s]+)(?:#(?P<item>[^)]+))?\)")
# 見出しのアンカーで落とす記号（mdmark の見出しの `id` と同じ）
ANCHOR_DROP = re.compile(r"[^\w\- ]")


def _choices(text: str) -> str | None:
    """値の全体が値の選択肢なら、値ごとのバッジと説明の行を返す。"""
    parts = text.split(CHOICE_SEPARATOR)
    matches = [CHOICE.match(part.strip()) for part in parts]
    if not all(matches):
        return None
    return "\n".join(f"- `badge:{m.group(1)}` {m.group(2)}" for m in matches if m)


def _tree(match: re.Match[str]) -> str:
    """言語の無いコードブロックが罫線のファイルツリーなら、言語を `tree` にする。"""
    lines = match.group(1).splitlines()
    is_tree = (
        len(lines) >= TREE_MIN_LINES
        and all(TREE_LINE.match(line) for line in lines)
        and any(TREE_BRANCH.search(line) for line in lines)
    )
    return f"```tree\n{match.group(1)}\n```" if is_tree else match.group(0)


def _is_steps(text: str) -> bool:
    """値の全体が番号付きの箇条書き（字下げの続きの行を含む）かを返す。"""
    lines = text.splitlines()
    if not lines or not STEP_LINE.match(lines[0]):
        return False
    return all(STEP_LINE.match(line) or line.startswith((" ", "\t")) for line in lines)


def _outside_code(text: str, rewrite: Callable[[str], str]) -> str:
    """コードブロック・行内のコードの外の部分だけを `rewrite` で書き換える。"""
    parts: list[str] = []
    position = 0
    for code in CODE_SPAN.finditer(text):
        parts.append(rewrite(text[position : code.start()]))
        parts.append(code.group(0))
        position = code.end()
    parts.append(rewrite(text[position:]))
    return "".join(parts)


def heading_anchor(text: str) -> str:
    """見出しの文字列を、その見出しへ飛ぶアンカー（`#` を除く）にする。"""
    return ANCHOR_DROP.sub("", text.strip().lower()).replace(" ", "-")


def _target(document_id: str, item: str, context: RenderContext) -> str | None:
    """文書の ID と項目のパスから、リンク先の相対パスとアンカー（引き先に無ければ `None`）を返す。"""
    link = context.links.get(document_id)
    if link is None:
        return None
    folder = posixpath.dirname(context.path) or "."
    relative = quote(posixpath.relpath(link.path, folder), safe="/")
    heading = context.item_heading(document_id, item) if item else None
    # 項目が見出しになる: その見出しのアンカーを付ける
    return f"{relative}#{heading_anchor(heading)}" if heading else relative


def _link_ids(text: str, context: RenderContext) -> str:
    """`id:` のリンクを、同じ配信元の文書への相対パスのリンクにする（引き先に無ければそのまま）。"""

    def replace(match: re.Match[str]) -> str:
        target = _target(match.group("id"), match.group("item") or "", context)
        return match.group(0) if target is None else f"[{match.group('name')}]({target})"

    return ID_LINK.sub(replace, text)


def rewrite_text(text: str, context: RenderContext, head: DiagramHead) -> str:
    """文字列の値の中の図・ファイルツリー・手順・Issue 番号・値の選択肢・id のリンクを mdmark の記法に書き換える。"""
    choices = _choices(text)
    if choices is not None:
        return choices
    text = MERMAID_BLOCK.sub(lambda match: render_mermaid(match.group(1), head), text)
    text = PLAIN_BLOCK.sub(_tree, text)
    if _is_steps(text):
        text = f"<!-- steps -->\n\n{text}\n\n<!-- /steps -->"
    issue_url = context.issue_url
    if issue_url is not None:
        text = _outside_code(text, lambda part: ISSUE_NUMBER.sub(rf"[#\1]({issue_url}\1)", part))
    return _outside_code(text, lambda part: _link_ids(part, context))


def _escape(text: str) -> str:
    """リンクの文字列の `[`・`]` をエスケープする。"""
    return text.replace("[", "\\[").replace("]", "\\]")


def link_reference(value: str, context: RenderContext) -> str | None:
    """`{ID}#{項目のパス}` の参照の値を、引き先の文書のタイトル付きのリンクにする（引き先に無ければ `None`）。"""
    document_id, _, item = value.partition("#")
    target = _target(document_id, item, context)
    if target is None:
        return None
    name = context.links[document_id].title
    title = f"{name} / {item}" if item else name
    return f"[{_escape(title)}]({target})"


def link_decisions(values: Sequence[Any], context: RenderContext) -> list[Any]:
    """`decisions` の並びのうち、文脈の `decisions` にある ID を検討事項の文書へのリンクの Markdown にする。"""
    folder = posixpath.dirname(context.path) or "."
    linked: list[Any] = []
    for value in values:
        # リンク先の決まる ID: 文書のフォルダから検討事項の文書のパスへの相対パスのリンク
        if isinstance(value, str) and value in context.decisions:
            relative = quote(posixpath.relpath(f"{DECISION_PAGE_PREFIX}{value}", folder), safe="/")
            linked.append(f"[{value}]({relative})")
        else:
            linked.append(value)
    return linked
