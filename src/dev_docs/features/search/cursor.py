"""検索の続きの位置。"""

from __future__ import annotations

import base64
import binascii
import json

from dev_docs.shared.errors import InvalidArgumentError, Violation

CURSOR_MESSAGE = "cursor は前回と同じ引数で渡してください"


def _invalid(rule: str) -> InvalidArgumentError:
    """`cursor` の違反 1 件の `InvalidArgumentError` を作る。"""
    return InvalidArgumentError(
        message=CURSOR_MESSAGE,
        violations=[
            Violation(path="cursor", rule=rule, fix="前回の next_cursor をそのまま渡してください")
        ],
    )


def encode_cursor(offset: int, fingerprint: str) -> str:
    """次の位置と要求の指紋を `next_cursor` の文字列にする。"""
    raw = json.dumps({"o": offset, "f": fingerprint}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str, fingerprint: str) -> int:
    """`cursor` から位置を取り出し、要求が前回と同じかを確かめる。"""
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        offset, saved = payload["o"], payload["f"]
    except (binascii.Error, ValueError, KeyError, TypeError) as error:
        raise _invalid("cursor を読めません") from error
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("cursor を読めません")
    if saved != fingerprint:
        raise _invalid("cursor は前回と別の引数で作られています")
    return offset
