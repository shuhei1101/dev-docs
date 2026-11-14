from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "build_pages.py"


@pytest.fixture
def build_pages() -> ModuleType:
    """`scripts/build_pages.py` をモジュールとして読み込んで返却する。"""
    spec = importlib.util.spec_from_file_location("build_pages", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass が自分のモジュールを sys.modules から参照するため、読み込む前に登録する
    sys.modules["build_pages"] = module
    spec.loader.exec_module(module)
    return module
