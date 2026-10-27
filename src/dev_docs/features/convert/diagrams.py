"""`x-diagram` の Mermaid の組み立て。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dev_docs.features.convert.types import DiagramKind


def render_diagram(value: Mapping[str, Any], kind: DiagramKind) -> str:
    """`x-diagram` の種類で、値から Mermaid の図を組み立てる。"""
    raise NotImplementedError
