"""例外から RFC 9457 の problem+json への変換。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from dev_docs.features.view.page import render_error_page
from dev_docs.shared.errors import DevDocsError, InvalidArgumentError
from dev_docs.shared.schema_check import format_path

logger = logging.getLogger(__name__)

PROBLEM_TYPE_BASE = "urn:dev-docs:error:"
PROBLEM_JSON = "application/problem+json"
BAD_REQUEST = 400
NOT_PARSEABLE_PARTS = ("body", "query", "path")


def _problem(name: str, status: int, detail: str, extra: dict[str, Any]) -> JSONResponse:
    """problem+json の応答を作る。"""
    body = {
        "type": f"{PROBLEM_TYPE_BASE}{name}",
        "title": name,
        "status": status,
        "detail": detail,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def register_error_handlers(app: FastAPI) -> None:
    """画面の API の例外を RFC 9457 の problem+json にするハンドラを登録する。"""

    @app.exception_handler(DevDocsError)
    async def dev_docs_error(request: Request, error: Exception) -> Response:
        assert isinstance(error, DevDocsError)  # noqa: S101
        handlers = getattr(request.app.state, "handlers", None)
        wants_html = request.method == "GET" and "text/html" in request.headers.get("accept", "")
        if wants_html and handlers is not None:
            return render_error_page(request, error, handlers=handlers)
        extra: dict[str, Any] = {"next_steps": error.next_steps, **error.details()}
        violations = getattr(error, "violations", None)
        if violations:
            extra["errors"] = [
                {"path": item.path, "reason": item.rule, **({"fix": item.fix} if item.fix else {})}
                for item in violations
            ]
        return _problem(error.name, error.status, error.message, extra)

    @app.exception_handler(RequestValidationError)
    async def request_invalid(request: Request, error: Exception) -> Response:
        assert isinstance(error, RequestValidationError)  # noqa: S101
        errors = [
            {
                "path": format_path(
                    part
                    for index, part in enumerate(item["loc"])
                    if not (index == 0 and part in NOT_PARSEABLE_PARTS)
                ),
                "reason": item["msg"],
            }
            for item in error.errors()
        ]
        return _problem(
            InvalidArgumentError.__name__,
            BAD_REQUEST,
            f"引数が正しくありません: {len(errors)} 件",
            {"next_steps": [], "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> Response:
        logger.error(
            "要求の処理に失敗した（%s・%s・%s）",
            request.method,
            request.url.path,
            error,
            exc_info=error,
        )
        return PlainTextResponse("Internal Server Error", status_code=500)
