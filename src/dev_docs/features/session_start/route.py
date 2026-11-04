"""`POST /_admin/session-start` のルート。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Body
from pydantic import ValidationError

from dev_docs.features.session_start.service import start_session
from dev_docs.features.session_start.types import SessionStartRequest, SessionStartResponse
from dev_docs.shared.errors import ValidationFailedError, Violation

if TYPE_CHECKING:
    from dev_docs.main import Handlers


def build_session_start_router(handlers: Handlers) -> APIRouter:
    """`POST /_admin/session-start` を持つルーターを作る。"""
    router = APIRouter()

    # フックは Origin を送信しないので同一オリジンの確認は掛けず、画面の API のスキーマにも載せない
    @router.post("/_admin/session-start", include_in_schema=False)
    async def post_session_start(
        payload: Annotated[dict[str, Any], Body()],
    ) -> SessionStartResponse:
        # 既存のハンドラーは本文の検証の失敗を 400 にするため、辞書で受けて自分で検証する
        try:
            request = SessionStartRequest.model_validate(payload)
        except ValidationError as error:
            violations = [
                Violation(path=".".join(str(part) for part in item["loc"]), rule=item["msg"])
                for item in error.errors()
            ]
            raise ValidationFailedError(
                message=f"セッションの開始の入力に違反が {len(violations)} 件あります",
                violations=violations,
            ) from error
        return await asyncio.to_thread(start_session, request, seen=handlers.seen)

    return router
