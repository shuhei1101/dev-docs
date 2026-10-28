"""抜粋の検索と、一致した箇所の抜き出し。"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from collections.abc import Sequence
from itertools import accumulate

from dev_docs.features.search.filters import compile_regex, normalize
from dev_docs.features.search.types import Condition, Snippet, SnippetLine

TEXT_OPS = ("eq", "prefix", "suffix", "contains")


def _split_lines(text: str) -> list[str]:
    """本文を行に分ける（行末の `\r` と、改行で終わる本文の最後の空の要素は除く）。"""
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    # 本文が改行で終わるときの最後の空の要素は行に数えない
    if text.endswith("\n"):
        lines.pop()
    return lines


def _regex_hits(lines: list[str], condition: Condition) -> set[int]:
    """`regex` の条件に当たった行の番号（0 始まり）を集める。"""
    # 区別しないときは行ごとに NFKC にして、行の対応を保つ
    folded = (
        lines
        if condition.case_sensitive
        else [unicodedata.normalize("NFKC", line) for line in lines]
    )
    whole = "\n".join(folded)
    # 各行の先頭の位置（改行の 1 文字を足す）
    starts = [0, *accumulate(len(line) + 1 for line in folded)][:-1]
    hits: set[int] = set()
    for value in condition.values:
        pattern = compile_regex(value, case_sensitive=condition.case_sensitive)
        for match in pattern.finditer(whole):
            first = bisect_right(starts, match.start()) - 1
            # 改行まで含めて当たっても次の行は当たりにしない
            last = bisect_right(starts, max(match.start(), match.end() - 1)) - 1
            hits.update(range(first, last + 1))
    return hits


def _text_hits(lines: list[str], condition: Condition) -> set[int]:
    """`eq`・`prefix`・`suffix`・`contains` の条件に値を含む行の番号（0 始まり）を集める。"""
    fold = (lambda text: text) if condition.case_sensitive else normalize
    wanted = [fold(value) for value in condition.values]
    return {index for index, line in enumerate(lines) if any(word in fold(line) for word in wanted)}


def find_snippets(
    text: str,
    conditions: Sequence[Condition],
    *,
    before: int,
    after: int,
    max_count: int,
) -> list[Snippet]:
    """本文から条件に当たる行と前後の行を、行番号つきの抜粋にする。"""
    lines = _split_lines(text)
    hits: set[int] = set()
    for condition in conditions:
        if condition.op == "regex":
            hits |= _regex_hits(lines, condition)
        elif condition.op in TEXT_OPS:
            hits |= _text_hits(lines, condition)
    # 当たった行ごとに前後の範囲を作り、重なる範囲は 1 つにまとめる
    ranges: list[list[int]] = []
    for index in sorted(hits):
        start, end = max(index - before, 0), min(index + after, len(lines) - 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    return [
        Snippet(
            lines=[
                SnippetLine(line=index + 1, text=lines[index], hit=index in hits)
                for index in range(start, end + 1)
            ]
        )
        for start, end in ranges[:max_count]
    ]


def snippet_lines(
    text: str, words: Sequence[str], *, context_lines: int, max_count: int
) -> list[str]:
    """本文から語を含む行と前後の行を抜き出す。"""
    condition = Condition(field="body", op="contains", values=list(words))
    snippets = find_snippets(
        text, [condition], before=context_lines, after=context_lines, max_count=max_count
    )
    return ["\n".join(line.text for line in snippet.lines) for snippet in snippets]
