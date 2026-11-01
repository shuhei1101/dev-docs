"""設定画面からの端末の設定の保存。"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from dev_docs.features.settings.query import load_terminal_config, validate_terminal_config
from dev_docs.features.settings.types import SourceEntry, TerminalConfig, TerminalConfigInvalidError
from dev_docs.features.sources.types import SourceStatus
from dev_docs.shared.files import replace_file
from dev_docs.shared.yaml_io import dump_roundtrip, load_roundtrip

logger = logging.getLogger(__name__)


def _to_yaml_row(entry: SourceEntry) -> dict[str, Any]:
    """既定値と同じキーを書かない `sources[]` の 1 行にする。"""
    row: dict[str, Any] = {}
    if entry.id is not None:
        row["id"] = entry.id
    row["config"] = list(entry.config)
    if not entry.enabled:
        row["enabled"] = False
    if not entry.outside_read:
        row["outside_read"] = False
    scope: dict[str, Any] = {}
    if entry.scope.read:
        scope["read"] = list(entry.scope.read)
    if entry.scope.write is not None:
        scope["write"] = list(entry.scope.write)
    if scope:
        row["scope"] = scope
    return row


def save_sources(
    sources: Sequence[SourceEntry],
    *,
    path: Path,
    reload: Callable[[TerminalConfig], list[SourceStatus]],
    lock: threading.Lock,
) -> list[SourceStatus]:
    """`settings.yaml` の `sources` だけを書き換え、検証に通ったら書いて配信元を読み直す。"""
    with lock:
        # sources だけを送られた行に置き換える（他のキーとコメントは保つ）
        document = load_roundtrip(path.read_text(encoding="utf-8"), file=str(path))
        document["sources"] = [_to_yaml_row(entry) for entry in sources]
        # 置き換えた後を検証し、違反があれば書かない
        plain = json.loads(json.dumps(document, default=str))
        violations = validate_terminal_config(plain)
        if violations:
            raise TerminalConfigInvalidError(
                file=path,
                message=f"{path}: 端末の設定に違反が {len(violations)} 件あります",
                violations=violations,
            )
        replace_file(path, dump_roundtrip(document))
        logger.info("端末の設定の sources を保存した（%s・%s 行）", path, len(sources))
        return reload(load_terminal_config(path))
