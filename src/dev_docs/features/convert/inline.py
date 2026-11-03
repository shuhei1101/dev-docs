"""文字列の値の本文の書き換えと、参照の値のリンクへの組み立て。"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import quote

from dev_docs.features.convert.diagrams import render_mermaid
from dev_docs.features.convert.types import DiagramHead, RenderContext

TREE_LINE = re.compile(r"^(\S.*|(│   |\|   |    )*(├── |└── |\|-- |`-- ).+)$")
TREE_BRANCH = re.compile(r"(├── |└── |\|-- |`-- )")
ISSUE_NUMBER = re.compile(r"(?<![\w/&\[])#(\d+)\b")
CHOICE = re.compile(r"^'([^']+)'（(.+)）$")
CHOICE_SEPARATOR = " / "
TREE_MIN_LINES = 2
MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)\n```", re.S)
PLAIN_BLOCK = re.compile(r"^```\n(.*?)\n```$", re.S | re.M)
STEP_LINE = re.compile(r"^\d+\. ")
# Issue 番号を書き換えない、コードブロックと行内のコード
CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.S)


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


def _link_issues(text: str, issue_url: str) -> str:
    """コードの外の Issue 番号を、Issue へのリンクにする。"""
    parts: list[str] = []
    position = 0
    for code in CODE_SPAN.finditer(text):
        parts.append(ISSUE_NUMBER.sub(rf"[#\1]({issue_url}\1)", text[position : code.start()]))
        parts.append(code.group(0))
        position = code.end()
    parts.append(ISSUE_NUMBER.sub(rf"[#\1]({issue_url}\1)", text[position:]))
    return "".join(parts)


def rewrite_text(text: str, context: RenderContext, head: DiagramHead) -> str:
    """文字列の値の中の図・ファイルツリー・手順・Issue 番号・値の選択肢を mdmark の記法に書き換える。"""
    choices = _choices(text)
    if choices is not None:
        return choices
    text = MERMAID_BLOCK.sub(lambda match: render_mermaid(match.group(1), head), text)
    text = PLAIN_BLOCK.sub(_tree, text)
    if _is_steps(text):
        text = f"<!-- steps -->\n\n{text}\n\n<!-- /steps -->"
    if context.issue_url is not None:
        text = _link_issues(text, context.issue_url)
    return text


def _escape(text: str) -> str:
    """リンクの文字列の `[`・`]` をエスケープする。"""
    return text.replace("[", "\\[").replace("]", "\\]")


def link_reference(value: str, context: RenderContext) -> str | None:
    """`{ID}#{項目のパス}` の参照の値を、引き先の文書のタイトル付きのリンクにする（引き先に無ければ `None`）。"""
    document_id, _, item = value.partition("#")
    link = context.links.get(document_id)
    if link is None:
        return None
    folder = posixpath.dirname(context.path) or "."
    relative = quote(posixpath.relpath(link.path, folder), safe="/")
    title = f"{link.title} / {item}" if item else link.title
    return f"[{_escape(title)}]({relative})"
