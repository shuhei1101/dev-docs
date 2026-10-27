"""例外から RFC 9457 の problem+json への変換。"""

from __future__ import annotations

from fastapi import FastAPI

PROBLEM_TYPE_BASE = "urn:dev-docs:error:"


def register_error_handlers(app: FastAPI) -> None:
    """画面の API の例外を RFC 9457 の problem+json にするハンドラを登録する。"""
    raise NotImplementedError
