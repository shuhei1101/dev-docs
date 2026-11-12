"""設計書の `decisions` の検討事項の ID と、検討事項の文書のパスの読み取り。"""

from __future__ import annotations

import re

DECISIONS_KEY = "decisions"
# AI Monitor の `共通.schema.yaml` の `decision` の `pattern` と同じ
DECISION_ID = re.compile(r"^[A-Z]+-[0-9]+$")
DECISION_PAGE_PREFIX = "_decisions/"


def decision_page_id(path: str) -> str | None:
    """文書の取得の `path` が検討事項の文書を指すなら、その検討事項の ID を返す。"""
    if not path.startswith(DECISION_PAGE_PREFIX):
        return None
    decision = path.removeprefix(DECISION_PAGE_PREFIX)
    return decision if DECISION_ID.fullmatch(decision) else None
