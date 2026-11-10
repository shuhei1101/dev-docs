"""端末の設定・4 つのメインのリポジトリの default_ref の設定・管理の MCP へ読み取りだけでつながるかを確かめる。"""

import sys

from mcp_client import ADMIN_MCP_URL, REPLACEMENTS, SETTINGS, config_at_default_ref, initialize


def admin_mcp_reachable() -> bool:
    """管理の MCP が initialize に応じるか。"""
    try:
        initialize(ADMIN_MCP_URL)
    except OSError:
        return False
    return True


def main() -> int:
    """対象ごとに結果の行を出す。"""
    results = [("端末の設定", SETTINGS.is_file())]
    results += [(new, config_at_default_ref(new)) for _, new in REPLACEMENTS]
    results.append(("管理の MCP", admin_mcp_reachable()))
    for name, ok in results:
        print(f"{name}: {'ok' if ok else 'failed'}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
