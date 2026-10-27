"""関連の候補の選択。"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from dev_docs.features.documents.types import Document
from dev_docs.features.related.types import Suggestion
from dev_docs.features.seen.types import Activity

SIGNAL_WEIGHTS = {"co_change": 1.0, "edited": 0.6, "viewed": 0.3}


def suggest_related(
    start: Sequence[Document],
    documents: Sequence[Document],
    *,
    exclude: Collection[str],
    co_changed: Mapping[str, int],
    activity: Sequence[Activity],
) -> list[Suggestion]:
    """同じ commit での変更と、この会話の編集・閲覧から関連の候補を選ぶ。"""
    raise NotImplementedError
