"""実行.py が退避した端末の設定を書き戻し、管理の MCP の reload で読み直す。"""

import os
import shutil
import sys

from mcp_client import ADMIN_MCP_URL, BACKUP, SETTINGS, call_tool


def main() -> int:
    """退避したファイルを戻して読み直し、手順ごとに結果の行を出す。"""
    if not BACKUP.is_file():
        print("退避したファイル: failed")
        return 1
    print("退避したファイル: ok")
    shutil.copy2(BACKUP, SETTINGS)
    os.remove(BACKUP)
    print("端末の設定の書き戻し: changed")
    try:
        call_tool(ADMIN_MCP_URL, "reload", {})
    except (OSError, RuntimeError) as error:
        print(f"読み直し: failed ({error})")
        return 1
    print("読み直し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
