"""画面と同じオリジンからの要求かの確認。"""

from __future__ import annotations

from fastapi import Request

SAME_ORIGIN = "same-origin"


def require_same_origin(request: Request) -> None:
    """画面と別のオリジンからの書き込みの要求を断る。"""
    raise NotImplementedError
