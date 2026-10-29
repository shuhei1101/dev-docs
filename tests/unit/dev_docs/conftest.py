from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.access.types import Target
from dev_docs.features.documents.types import Document
from dev_docs.features.settings.query import load_terminal_config
from dev_docs.features.settings.types import SourceEntry, SourceScope, TerminalConfig
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import (
    DocumentTable,
    ScriptEntry,
    ServedSource,
    SourceConfig,
    SourceStatus,
)
from dev_docs.main import Handlers, build_handlers
from dev_docs.shared.errors import UnknownSourceError

SAMPLE_SCHEMA = (
    "title: rule\n"
    "type: object\n"
    "properties:\n"
    "  id: {type: string}\n"
    "  name: {type: string}\n"
    "required: [id, name]\n"
)

SAMPLE_CONFIG = (
    "name: sample\n"
    "documents:\n"
    "  - id: rules\n"
    "    paths: [docs/rule/*.yaml]\n"
    "    schema: schemas/rule.schema.yaml\n"
)


@pytest.fixture
def sample_files() -> dict[str, str]:
    """検証を通る最小の配信元のファイル一式（設定・スキーマ・文書 2 件）を返す。"""
    return {
        "dev-docs.yaml": SAMPLE_CONFIG,
        "schemas/rule.schema.yaml": SAMPLE_SCHEMA,
        "docs/rule/doc-1.yaml": "id: doc-1\nname: 文書 1\n",
        "docs/rule/doc-2.yaml": "id: doc-2\nname: 文書 2\n",
    }


@pytest.fixture
def make_terminal_config(tmp_path: Path) -> Callable[..., TerminalConfig]:
    """端末の設定を作る関数を返す。"""

    def _make(**overrides: Any) -> TerminalConfig:
        state_dir = overrides.pop("state_dir", tmp_path / "state")
        values: dict[str, Any] = {
            "file": tmp_path / "settings.yaml",
            "version": "1",
            "clone": tmp_path / "clone",
            "state_dir": state_dir,
            "log_dir": state_dir / "logs",
        }
        values.update(overrides)
        return TerminalConfig(**values)

    return _make


@pytest.fixture
def make_entry() -> Callable[..., SourceEntry]:
    """端末の設定の `sources[]` の行を作る関数を返す。"""

    def _make(
        config: str | list[str], *, source_id: str | None = None, **overrides: Any
    ) -> SourceEntry:
        paths = [config] if isinstance(config, str) else config
        scope = overrides.pop("scope", SourceScope())
        return SourceEntry(id=source_id, config=paths, scope=scope, **overrides)

    return _make


@pytest.fixture
def make_source_config() -> Callable[..., SourceConfig]:
    """配信元の設定を作る関数を返す。"""

    def _make(**overrides: Any) -> SourceConfig:
        values: dict[str, Any] = {
            "name": "sample",
            "documents": [
                DocumentTable(
                    id="rules",
                    paths=["docs/rule/*.yaml"],
                    schema_path="schemas/rule.schema.yaml",
                )
            ],
        }
        values.update(overrides)
        return SourceConfig(**values)

    return _make


@pytest.fixture
def make_served_source(
    tmp_path: Path, make_source_config: Callable[..., SourceConfig]
) -> Callable[..., ServedSource]:
    """配信中の配信元を作る関数を返す。"""

    def _make(**overrides: Any) -> ServedSource:
        root = overrides.pop("root", tmp_path / "sample")
        values: dict[str, Any] = {
            "id": "sample",
            "root": root,
            "config_files": [root / "dev-docs.yaml"],
            "config": make_source_config(),
            "is_git": False,
            "repo_root": None,
            "scope_read": [],
            "scope_write": [str(root)],
            "worktree_globs": [],
            "schemas": {},
            "tag_master": {},
        }
        values.update(overrides)
        return ServedSource(**values)

    return _make


@pytest.fixture
def make_status() -> Callable[..., SourceStatus]:
    """配信元の状態を作る関数を返す。"""

    def _make(
        source_id: str, index: int, status: str = "serving", **overrides: Any
    ) -> SourceStatus:
        return SourceStatus(id=source_id, index=index, status=status, **overrides)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_script() -> Callable[..., ScriptEntry]:
    """スクリプトの行を作る関数を返す。"""

    def _make(script_id: str, *run: str) -> ScriptEntry:
        return ScriptEntry(id=script_id, run=list(run))

    return _make


@pytest.fixture
def make_handlers(make_terminal_config: Callable[..., TerminalConfig]) -> Callable[..., Any]:
    """指定した部品だけ偽物にした配線済みの関数を作る関数を返す。"""
    import dataclasses
    import threading

    from dev_docs.main import Handlers

    def _make(**overrides: Any) -> Handlers:
        values: dict[str, Any] = {field.name: None for field in dataclasses.fields(Handlers)}
        values.update(
            {
                "terminal": make_terminal_config(),
                "settings_lock": threading.Lock(),
                "reload_sources": lambda terminal: [],
            }
        )
        values.update(overrides)
        return Handlers(**values)

    return _make


class FakeRegistry(SourceRegistry):
    """決めた配信元を返す配信元の一覧の偽物。"""

    def __init__(self, sources: list[ServedSource]) -> None:
        super().__init__()
        self._sources = sources

    def served(self) -> list[ServedSource]:
        return list(self._sources)

    def get(self, source_id: str) -> ServedSource:
        matches = [source for source in self._sources if source.id == source_id]
        if not matches:
            raise UnknownSourceError(
                message=f"配信元 {source_id} はありません", source_id=source_id
            )
        return matches[0]

    def statuses(self) -> list[SourceStatus]:
        return [
            SourceStatus(id=source.id, index=index, status="serving")
            for index, source in enumerate(self._sources)
        ]


@pytest.fixture
def make_registry() -> Callable[..., FakeRegistry]:
    """配信元の一覧の偽物を作る関数を返す。"""

    def _make(*sources: ServedSource) -> FakeRegistry:
        return FakeRegistry(list(sources))

    return _make


@pytest.fixture
def make_target() -> Callable[..., Target]:
    """読み書きの場所を作る関数を返す。"""

    def _make(source: ServedSource, **overrides: Any) -> Target:
        values: dict[str, Any] = {
            "source": source,
            "base": source.root,
            "ref": None,
            "worktree": None,
            "access": "write",
        }
        values.update(overrides)
        return Target(**values)

    return _make


@pytest.fixture
def make_document() -> Callable[..., Document]:
    """文書を作る関数を返す。"""

    def _make(**overrides: Any) -> Document:
        values: dict[str, Any] = {
            "id": "doc-1",
            "kind": "rules",
            "source_id": "sample",
            "path": "rules/doc-1.yaml",
            "record_index": None,
            "data": {"id": "doc-1", "name": "文書 1"},
            "body": "id: doc-1\nname: 文書 1\n",
            "body_path": None,
            "metadata": {"id": "doc-1", "name": "文書 1"},
            "version": "9d0e11",
            "created": None,
            "updated": None,
        }
        values.update(overrides)
        return Document(**values)

    return _make


FILES_SCHEMA = "title: file\ntype: object\n"

SOURCE_CONFIG_TEMPLATE = (
    "name: {name}\n"
    "{version}"
    "documents:\n"
    "  - id: rules\n"
    "    paths: [docs/rule/*.yaml]\n"
    "    schema: schemas/rule.schema.yaml\n"
)

FILES_ROW = (
    "  - id: src\n"
    "    paths: [src/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)


@pytest.fixture
def make_source_dir(
    tmp_path: Path, write_files: Callable[[Path, dict[str, str]], None]
) -> Callable[..., Path]:
    """検証を通る配信元のフォルダを作り、`dev-docs.yaml` のパスを返す関数を返す。

    `unindexed` は管理用の YAML に無いファイルの数、`version` は設定の `version`。
    """

    def _make(name: str, *, unindexed: int = 0, version: str | None = None) -> Path:
        root = tmp_path / name
        version_line = "" if version is None else f'version: "{version}"\n'
        config = SOURCE_CONFIG_TEMPLATE.format(name=name, version=version_line)
        files = {
            "schemas/rule.schema.yaml": SAMPLE_SCHEMA,
            "docs/rule/doc-1.yaml": "id: doc-1\nname: 文書 1\n",
        }
        if unindexed:
            config += FILES_ROW
            files["schemas/files.schema.yaml"] = FILES_SCHEMA
            files["src/files.yaml"] = "files:\n  - path: a.py\n"
            files["src/a.py"] = "a = 1\n"
            files.update({f"src/u{index}.py": "x = 1\n" for index in range(unindexed)})
        files["dev-docs.yaml"] = config
        write_files(root, files)
        return root / "dev-docs.yaml"

    return _make


@pytest.fixture
def write_settings(tmp_path: Path) -> Callable[..., Path]:
    """端末の設定をファイルに書き、そのパスを返す関数を返す（JSON は YAML として読める）。"""

    def _write(sources: list[dict[str, Any]], **top: Any) -> Path:
        values: dict[str, Any] = {
            "version": "1",
            "clone": str(tmp_path / "clone"),
            "state_dir": str(tmp_path / "state"),
            "sources": sources,
        }
        values.update(top)
        path = tmp_path / "settings.yaml"
        path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def make_real_handlers() -> Callable[[Path], Handlers]:
    """端末の設定のファイルを読み、部品を本物で配線した配線済みの関数を作る関数を返す。"""

    def _make(settings: Path) -> Handlers:
        return build_handlers(load_terminal_config(settings))

    return _make


@pytest.fixture
def migrations_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """移し替えの手順の置き場所を一時のフォルダに差し替え、そのフォルダを返す。

    絶対パスを手順のフォルダの名前に差し替えると、パッケージのフォルダにつないでも絶対パスが残る。
    """
    root = tmp_path / "migrations"
    root.mkdir()
    monkeypatch.setattr("dev_docs.features.migrate.types.MIGRATIONS_DIR", str(root))
    monkeypatch.setattr("dev_docs.features.migrate.steps.MIGRATIONS_DIR", str(root), raising=False)
    return root


@pytest.fixture
def write_steps(migrations_root: Path) -> Callable[..., None]:
    """移し替えの手順のファイル（`{kind}/{バージョン}/steps.yaml`）を書く関数を返す。"""

    def _write(kind: str, version: str, steps: list[dict[str, Any]]) -> None:
        target = migrations_root / kind / version / "steps.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"steps": steps}, ensure_ascii=False), encoding="utf-8")

    return _write


@pytest.fixture
def settings_version_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev-docs が読める端末の設定のバージョンを `2` に差し替える。"""
    monkeypatch.setattr("dev_docs.features.settings.query.SETTINGS_VERSION", "2")
    for target in (
        "dev_docs.features.migrate.service.SETTINGS_VERSION",
        "dev_docs.features.admin.service.SETTINGS_VERSION",
        "dev_docs.main.SETTINGS_VERSION",
    ):
        monkeypatch.setattr(target, "2", raising=False)
