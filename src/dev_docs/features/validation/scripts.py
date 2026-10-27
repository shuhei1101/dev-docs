"""`validators[]` の出力の解釈。"""

from __future__ import annotations

from dev_docs.shared.errors import Violation


def parse_validator_output(stdout: str, *, validator_id: str) -> list[Violation]:
    """`validators[]` の標準出力の JSON を違反の並びにする。"""
    raise NotImplementedError
