"""PreToolUse のフック: 入力の cwd・session_id・agent_id を MCP ツールの引数へ重ねる（H1: permissionDecision なし）。

Usage:
# Claude Code が標準入力にフックの入力の JSON を渡す。POC_LOG_DIR に hook.jsonl を書く
python3 inject.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """フックの入力を記録し、値を重ねた updatedInput を出す。"""
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})

    # 測定のため、フックが見た値を全て残す
    record = {
        "tool_name": payload.get("tool_name"),
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id"),
        "agent_type": payload.get("agent_type"),
        "claude_project_dir": os.environ.get("CLAUDE_PROJECT_DIR"),
        "tool_input": tool_input,
    }
    log = Path(os.environ["POC_LOG_DIR"]) / "hook.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # モデルが渡した値を、フックの入力の値で上書きする
    updated = {
        **tool_input,
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id") or "",
    }
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
