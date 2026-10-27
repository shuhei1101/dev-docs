"""検索の続きの位置。"""

from __future__ import annotations


def encode_cursor(offset: int, fingerprint: str) -> str:
    """次の位置と要求の指紋を `next_cursor` の文字列にする。"""
    raise NotImplementedError


def decode_cursor(cursor: str, fingerprint: str) -> int:
    """`cursor` から位置を取り出し、要求が前回と同じかを確かめる。"""
    raise NotImplementedError
