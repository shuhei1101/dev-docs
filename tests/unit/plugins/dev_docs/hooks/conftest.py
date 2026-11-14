from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).parents[5] / "plugins" / "dev-docs" / "hooks"


@pytest.fixture
def load_hook() -> Callable[[str], ModuleType]:
    """プラグインのフックのファイルを、ファイル名からモジュールとして読み込む関数を返却する。"""

    def _load(name: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"hook_{name}", HOOKS_DIR / f"{name}.py")
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return _load
