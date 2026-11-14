"""画面の API の OpenAPI を frontend/openapi.json に書き出す（orval の入力）。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from dev_docs.server.app import build_app

OUTPUT = Path(__file__).parent.parent / "openapi.json"


def main() -> None:
    """ルートの定義だけを使用するので、配線済みの関数は偽物でよい。"""
    handlers = MagicMock()
    # MCP のツールの description は文字列でないと登録できない
    handlers.prompts.render.return_value = ""
    app = build_app(handlers)
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
