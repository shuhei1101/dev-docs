from __future__ import annotations

import pytest
from starlette.requests import Request

from dev_docs.server.origin import require_same_origin
from dev_docs.shared.errors import CrossOriginError


def _request(headers: dict[str, str]) -> Request:
    """ホストを 127.0.0.1:8781 にした PUT の要求を組み立てる。"""
    all_headers = {"host": "127.0.0.1:8781", **headers}
    scope = {
        "type": "http",
        "method": "PUT",
        "scheme": "http",
        "server": ("127.0.0.1", 8781),
        "path": "/_api/settings/sources",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in all_headers.items()],
    }
    return Request(scope)


def test_require_same_origin() -> None:
    """同じオリジン（正常系）。"""
    # 準備
    request = _request({"origin": "http://127.0.0.1:8781"})
    # 実行・検証
    require_same_origin(request)


def test_require_same_origin_when_fetch_site() -> None:
    """`Origin` が無く `Sec-Fetch-Site` が same-origin（正常系）。"""
    # 準備
    request = _request({"sec-fetch-site": "same-origin"})
    # 実行・検証
    require_same_origin(request)


def test_require_same_origin_when_cross_origin() -> None:
    """別のオリジン（異常系）。"""
    # 準備
    request = _request({"origin": "http://evil.example"})
    # 実行・検証
    with pytest.raises(CrossOriginError) as exc_info:
        require_same_origin(request)
    assert "evil.example" in exc_info.value.message


def test_require_same_origin_when_unknown() -> None:
    """どちらのヘッダーも無い（異常系）。"""
    # 準備
    request = _request({})
    # 実行・検証
    with pytest.raises(CrossOriginError) as exc_info:
        require_same_origin(request)
    assert "確かめられません" in exc_info.value.message
