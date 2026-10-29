"""パッケージに入れた移し替えの手順を読み、メモリの上の YAML に当てる。"""

from __future__ import annotations

from importlib import resources
from typing import Any, Literal, cast

from ruamel.yaml.comments import CommentedMap

from dev_docs.features.migrate.types import (
    MIGRATIONS_DIR,
    STEPS_FILE,
    MigrationFailedError,
    MigrationStep,
)
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

OPERATIONS = ("rename", "add", "delete")
ARRAY_SUFFIX = "[]"


def load_steps(
    kind: Literal["settings", "dev-docs"], *, mine: str, current: str
) -> list[MigrationStep]:
    """対象のバージョンより新しく読めるバージョン以下の手順を、古い順に読む。"""
    root = resources.files("dev_docs") / MIGRATIONS_DIR / kind
    if not root.is_dir():
        return []
    versions = sorted(
        int(entry.name)
        for entry in root.iterdir()
        if entry.name.isdecimal() and int(mine) < int(entry.name) <= int(current)
    )
    steps: list[MigrationStep] = []
    for number in versions:
        name = str(number)
        steps.extend(_read_version(root / name / STEPS_FILE, name))
    return steps


def _read_version(file: Any, version: str) -> list[MigrationStep]:
    """1 つのバージョンの `steps.yaml` を手順にする。"""
    label = f"{version}/{STEPS_FILE}"
    try:
        value = load_yaml(file.read_text(encoding="utf-8"), file=label)
    except (OSError, YamlLoadError) as error:
        raise MigrationFailedError(f"{label}: {error}") from error
    rows = value.get("steps") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise MigrationFailedError(f"{label}: steps の並びがありません")
    steps: list[MigrationStep] = []
    for row in rows:
        # 操作は選択肢の中だけ。改名は新しいキーを持つ
        if not isinstance(row, dict) or row.get("op") not in OPERATIONS:
            raise MigrationFailedError(f"{label}: op は {'・'.join(OPERATIONS)} のどれかです")
        if row["op"] == "rename" and not row.get("to"):
            raise MigrationFailedError(f"{label}: rename には to が要ります（{row.get('path')}）")
        steps.append(
            MigrationStep(
                version=version,
                op=row["op"],
                path=str(row.get("path", "")),
                description=str(row.get("description", "")),
                to=row.get("to"),
                value=row.get("value"),
            )
        )
    return steps


def _parents(data: CommentedMap, parts: list[str]) -> list[CommentedMap]:
    """キーのパスの末尾の手前までをたどり、末尾のキーを持つ親の辞書を集める。"""
    parents: list[CommentedMap] = [data]
    for part in parts:
        next_parents: list[CommentedMap] = []
        for parent in parents:
            # `{キー}[]` は配列の要素ごとにたどる
            key = part.removesuffix(ARRAY_SUFFIX)
            child = parent.get(key)
            if part.endswith(ARRAY_SUFFIX):
                if isinstance(child, list):
                    next_parents.extend(item for item in child if isinstance(item, CommentedMap))
            elif isinstance(child, CommentedMap):
                next_parents.append(child)
        parents = next_parents
    return parents


def _rename(parent: CommentedMap, step: MigrationStep, key: str) -> None:
    """同じ位置・同じコメントでキーを改名する。"""
    to = cast("str", step.to)
    if to in parent:
        raise MigrationFailedError(
            f"{step.version}: {step.path} を {to} に改名できません（{to} があります）"
        )
    position = list(parent).index(key)
    comment = parent.ca.items.pop(key, None)
    value = parent.pop(key)
    parent.insert(position, to, value)
    if comment is not None:
        parent.ca.items[to] = comment


def apply_step(data: CommentedMap, step: MigrationStep) -> None:
    """メモリの上の YAML に 1 つの手順を当てる。"""
    *parents_path, key = step.path.split(".")
    for parent in _parents(data, parents_path):
        # 操作ごとに分ける（キーが無い親では何もしない）
        if step.op == "rename":
            if key in parent:
                _rename(parent, step, key)
        elif step.op == "add":
            if key not in parent:
                parent[key] = step.value
        elif key in parent:
            del parent[key]
