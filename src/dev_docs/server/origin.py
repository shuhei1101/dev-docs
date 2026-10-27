"""画面と同じオリジンからの要求かの確認。"""

from __future__ import annotations

from fastapi import Request

from dev_docs.shared.errors import CrossOriginError

SAME_ORIGIN = "same-origin"


def require_same_origin(request: Request) -> None:
    """画面と別のオリジンからの書き込みの要求を断る。"""
    origin = request.headers.get("origin")
    if origin is not None:
        own = f"{request.url.scheme}://{request.url.netloc}"
        # Origin が画面のオリジンと違う
        if origin != own:
            raise CrossOriginError(message=f"画面と別のオリジン（{origin}）からの要求は受けません")
        return
    # Origin が無いときは Sec-Fetch-Site で確かめる
    if request.headers.get("sec-fetch-site") != SAME_ORIGIN:
        raise CrossOriginError(message="画面と同じオリジンからの要求か確かめられません")
