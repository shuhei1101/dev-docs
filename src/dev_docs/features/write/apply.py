"""項目の操作を当てる。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dev_docs.features.write.types import Operation


def apply_operation(current: Mapping[str, Any] | None, operation: Operation) -> dict[str, Any]:
    """文書の内容に 1 件の操作を当てた新しい内容を返す。"""
    raise NotImplementedError
