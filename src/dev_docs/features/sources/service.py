"""配信元の読み込みと検証。"""

from __future__ import annotations

import json
import logging
import os
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator

from dev_docs.features.settings.types import SourceEntry
from dev_docs.features.sources.merge import merge_configs
from dev_docs.features.sources.types import (
    SOURCE_CONFIG_VERSION,
    DocumentTable,
    ScriptEntry,
    ServedSource,
    SourceConfig,
    SourceStatus,
)
from dev_docs.integrations.git import repo_root as git_repo_root
from dev_docs.integrations.scripts import ScriptNotFoundError, check_runnable
from dev_docs.shared.errors import ValidationFailedError, Violation
from dev_docs.shared.schema_check import schema_violations
from dev_docs.shared.yaml_io import YamlLoadError, load_yaml

logger = logging.getLogger(__name__)

SOURCE_SCHEMA = "schemas/dev-docs.schema.yaml"
SCRIPT_TABLES = ("validators", "converters", "generators")

__all__ = [
    "SOURCE_CONFIG_VERSION",
    "SOURCE_SCHEMA",
    "assemble_source",
    "build_source_config",
    "check_scripts",
    "compare_config_version",
    "load_source",
    "load_source_at",
    "source_schema_json",
    "validate_source_config",
]


def _source_schema() -> dict[str, Any]:
    """配布に同梱した配信元の設定のスキーマを読む。"""
    text = resources.files("dev_docs").joinpath(SOURCE_SCHEMA).read_text(encoding="utf-8")
    schema: dict[str, Any] = load_yaml(text)
    return schema


def source_schema_json() -> str:
    """配信元の設定のスキーマを、配布する JSON Schema の文字列にする。"""
    return json.dumps(_source_schema(), ensure_ascii=False, indent=2) + "\n"


def _outside_root(pattern: str) -> bool:
    """パスが `..` で配信元の外を指すか。"""
    return ".." in Path(pattern).parts


def _file_violation(root: Path, key_path: str, relative: str, what: str) -> Violation | None:
    """設定が指すファイルが配信元の下にあり、YAML として読めるかを確かめる。"""
    target = root / relative
    if _outside_root(relative):
        return Violation(path=key_path, rule=f"配信元の外を指しています: {relative}")
    if not target.is_file():
        return Violation(path=key_path, rule=f"{what}のファイルが無い: {relative}")
    try:
        load_yaml(target.read_text(encoding="utf-8"), file=relative)
    except YamlLoadError as error:
        return Violation(path=key_path, rule=f"{what}を YAML として読めない: {error}")
    return None


def validate_source_config(value: dict[str, Any], *, root: Path) -> list[Violation]:
    """マージした設定をスキーマ・行の参照・ファイルの有無で確かめ、違反を全て返す。"""
    violations = schema_violations(_source_schema(), value)
    # スキーマの違反があれば、ここで返す
    if violations:
        return violations
    documents: list[dict[str, Any]] = value.get("documents", [])
    # テーブルごとに ID の重なりを確かめる
    tables = {"documents": documents}
    tables.update({name: value.get(name, []) for name in SCRIPT_TABLES})
    for name, rows in tables.items():
        seen: set[str] = set()
        for index, row in enumerate(rows):
            if row["id"] in seen:
                violations.append(
                    Violation(path=f"{name}[{index}].id", rule=f"ID が重なっています: {row['id']}")
                )
            seen.add(row["id"])
    # 行の参照が、無い ID を指していないか
    ids = {name: {row["id"] for row in value.get(name, [])} for name in SCRIPT_TABLES}
    references = (
        ("validators", "validators"),
        ("converter", "converters"),
        ("after_write", "generators"),
    )
    for index, row in enumerate(documents):
        for key, table in references:
            refs = row.get(key, [])
            targets = [refs] if isinstance(refs, str) else refs
            for position, ref in enumerate(targets):
                if ref not in ids[table]:
                    path = f"documents[{index}].{key}"
                    if key != "converter":
                        path += f"[{position}]"
                    violations.append(
                        Violation(
                            path=path,
                            rule="存在しない ID",
                            fix=f"{table}[] の ID を指してください: {ref}",
                        )
                    )
        if "body_file" in row and "records" not in row:
            violations.append(
                Violation(
                    path=f"documents[{index}].body_file", rule="records と一緒に書いてください"
                )
            )
        # ファイルの有無と配信元の外を指すパス
        for position, pattern in enumerate(row["paths"]):
            if _outside_root(pattern):
                violations.append(
                    Violation(
                        path=f"documents[{index}].paths[{position}]",
                        rule=f"配信元の外を指しています: {pattern}",
                    )
                )
        found = _file_violation(root, f"documents[{index}].schema", row["schema"], "スキーマ")
        if found is None:
            found = _check_schema_file(root, f"documents[{index}].schema", row["schema"])
        if found is not None:
            violations.append(found)
    return violations


def _check_schema_file(root: Path, key_path: str, relative: str) -> Violation | None:
    """スキーマのファイルが JSON Schema（Draft 2020-12）として正しいかを確かめる。"""
    schema = load_yaml((root / relative).read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        return Violation(path=key_path, rule=f"スキーマが正しくありません: {error.message}")
    return None


def check_scripts(config: SourceConfig, *, root: Path) -> list[Violation]:
    """検査・変換・生成の行のコマンドを動かさずに確かめる。"""
    violations: list[Violation] = []
    for table in SCRIPT_TABLES:
        for index, row in enumerate(getattr(config, table)):
            try:
                check_runnable(row.run, cwd=root)
            except ScriptNotFoundError as error:
                violations.append(Violation(path=f"{table}[{index}]", rule=error.reason))
    return violations


def compare_config_version(version: str) -> Literal["same", "older", "newer"]:
    """配信元の設定のバージョンをサーバーの読めるバージョンと比べる。"""
    mine, current = int(version), int(SOURCE_CONFIG_VERSION)
    if mine == current:
        return "same"
    return "older" if mine < current else "newer"


def build_source_config(value: dict[str, Any]) -> SourceConfig:
    """検証を通した設定の値から `SourceConfig` を作る。"""
    ids = value.get("ids", {})
    related = value.get("related", {})
    diff = value.get("diff", {})
    github = value.get("github", {})
    options: dict[str, Any] = {}
    for key in ("version", "enabled", "default_ref", "visibility", "worktrees", "nav"):
        if key in value:
            options[key] = value[key]
    if "types" in related:
        options["related_types"] = list(related["types"])
    if "ignore_keys" in diff:
        options["diff_ignore_keys"] = list(diff["ignore_keys"])
    if "repository" in github:
        options["github_repository"] = github["repository"]
    if "issue_labels" in github:
        options["github_issue_labels"] = list(github["issue_labels"])
    if "format" in ids:
        options["ids_format"] = ids["format"]
    return SourceConfig(
        name=value["name"],
        description=value.get("description", ""),
        instructions=value.get("instructions", ""),
        documents=[_build_table(row) for row in value.get("documents", [])],
        validators=[_build_script(row) for row in value.get("validators", [])],
        converters=[_build_script(row) for row in value.get("converters", [])],
        generators=[_build_script(row) for row in value.get("generators", [])],
        **options,
    )


def _build_script(row: dict[str, Any]) -> ScriptEntry:
    """スクリプトの行を作る。"""
    return ScriptEntry(id=row["id"], run=list(row["run"]), on=list(row.get("on", ["write"])))


def _build_table(row: dict[str, Any]) -> DocumentTable:
    """文書の行を作る。"""
    return DocumentTable(
        id=row["id"],
        paths=list(row["paths"]),
        schema_path=row["schema"],
        title=row.get("title"),
        enabled=row.get("enabled", True),
        validators=list(row.get("validators", [])),
        converter=row.get("converter"),
        writable=row.get("writable"),
        after_write=list(row.get("after_write", [])),
        search=row.get("search", True),
        records=row.get("records"),
        body_file=row.get("body_file"),
        metadata=dict(row.get("metadata", {})),
        exclude=list(row.get("exclude", [])),
        alias_type=row.get("alias_type"),
    )


def _read_configs(files: list[Path]) -> tuple[list[dict[str, Any]], list[Violation]]:
    """設定の YAML を順に読む。無い・読めない・辞書でないファイルは違反にする。"""
    values: list[dict[str, Any]] = []
    violations: list[Violation] = []
    for index, file in enumerate(files):
        path = f"config[{index}]"
        if not file.is_file():
            violations.append(Violation(path=path, rule=f"設定のファイルが無い: {file}"))
            continue
        try:
            value = load_yaml(file.read_text(encoding="utf-8"), file=str(file))
        except YamlLoadError as error:
            violations.append(Violation(path=path, rule=f"YAML として読めない: {error}"))
            continue
        if not isinstance(value, dict):
            violations.append(Violation(path=path, rule=f"最上位が辞書ではない: {file}"))
            continue
        values.append(value)
    return values, violations


def _worktree_globs(patterns: list[str], base: Path) -> list[str]:
    """`worktrees` の glob を、リポジトリの直下からの絶対パスにする。"""
    result: list[str] = []
    for pattern in patterns:
        expanded = Path(pattern).expanduser()
        joined = expanded if expanded.is_absolute() else base / expanded
        result.append(os.path.normpath(joined.as_posix()))
    return result


def assemble_source(
    files: list[Path],
    *,
    source_id: str | None,
    scope_read: list[str],
    scope_write: list[str] | None,
    root_override: Path | None = None,
) -> tuple[ServedSource | None, SourceConfig | None, list[Violation]]:
    """設定を読み、マージ・検証・スクリプトの確かめをして、配信中の配信元を作る。"""
    values, violations = _read_configs(files)
    if violations:
        return None, None, violations
    root = root_override or files[0].parent
    merged = merge_configs(values)
    violations = validate_source_config(merged, root=root)
    if violations:
        return None, None, violations
    config = build_source_config(merged)
    violations = check_scripts(config, root=root)
    if violations:
        return None, config, violations
    top = git_repo_root(root)
    base = top or root
    schemas = {
        row.id: load_yaml((root / row.schema_path).read_text(encoding="utf-8"))
        for row in config.documents
    }
    served = ServedSource(
        id=source_id or config.name,
        root=root,
        config_files=files,
        config=config,
        is_git=top is not None,
        repo_root=top,
        scope_read=list(scope_read),
        scope_write=list(scope_write) if scope_write else [str(root)],
        worktree_globs=_worktree_globs(config.worktrees, base),
        schemas=schemas,
    )
    return served, config, []


def _log_violations(source_id: str, violations: list[Violation]) -> None:
    """配信しない理由を、違反ごとに `{id}: {パス}: {理由}` でエラーログに書く。"""
    for violation in violations:
        logger.error("%s: %s: %s", source_id, violation.path, violation.rule)


def _declared_version(files: list[Path]) -> str | None:
    """マージした設定が書いている `version`。読めない・書いていなければ `None`。"""
    values, violations = _read_configs(files)
    if violations:
        return None
    version = merge_configs(values).get("version")
    return version if isinstance(version, str) and version.isdecimal() else None


def load_source(entry: SourceEntry, *, index: int) -> tuple[ServedSource | None, SourceStatus]:
    """端末の設定の 1 行から配信元の設定を読んで検証し、配信中の配信元と状態を作る。"""
    fallback_id = entry.id or f"sources[{index}]"
    config_files = tuple(entry.config)
    # 端末の設定で無効な行は、設定を読まない
    if not entry.enabled:
        return None, SourceStatus(
            id=fallback_id, index=index, status="disabled", config=config_files
        )
    files = [Path(item).expanduser() for item in entry.config]
    served, config, violations = assemble_source(
        files,
        source_id=entry.id,
        scope_read=entry.scope.read,
        scope_write=entry.scope.write,
    )
    source_id = entry.id or (config.name if config else fallback_id)
    if violations:
        _log_violations(source_id, violations)
        declared = _declared_version(files)
        if declared is not None and compare_config_version(declared) == "older":
            logger.error(
                "%s: 設定のバージョンが古いので、dev-docs migrate --source %s で移し替えられます",
                source_id,
                files[0],
            )
        return None, SourceStatus(
            id=source_id, index=index, status="not_served", errors=violations, config=config_files
        )
    assert served is not None and config is not None  # noqa: S101
    # 配信元の設定で無効
    if not config.enabled:
        return None, SourceStatus(id=source_id, index=index, status="disabled", config=config_files)
    # 設定のバージョンを比べる
    comparison = compare_config_version(config.version)
    if comparison == "newer":
        violations = [Violation(path="version", rule="このサーバーより新しい設定です")]
        _log_violations(source_id, violations)
        return None, SourceStatus(
            id=source_id, index=index, status="not_served", errors=violations, config=config_files
        )
    config_version: tuple[str, str] | None = None
    if comparison == "older":
        config_version = (config.version, SOURCE_CONFIG_VERSION)
        logger.warning(
            "配信元の設定のバージョンが古い（%s・設定 %s・サーバーが読める %s）",
            source_id,
            config.version,
            SOURCE_CONFIG_VERSION,
        )
    return served, SourceStatus(
        id=source_id,
        index=index,
        status="serving",
        config_version=config_version,
        config=config_files,
    )


def load_source_at(source: ServedSource, root: Path) -> ServedSource:
    """配信中の配信元の設定を、作業ツリーかワークツリーの同じ場所から読み直す。"""
    base = source.repo_root or source.root
    files: list[Path] = []
    for file in source.config_files:
        try:
            files.append(root / file.relative_to(base))
        except ValueError:
            # 配信元のリポジトリの外のファイルはそのまま使う
            files.append(file)
    relative_root = source.root.relative_to(base) if source.root.is_relative_to(base) else Path()
    served, _, violations = assemble_source(
        files,
        source_id=source.id,
        scope_read=source.scope_read,
        scope_write=source.scope_write,
        root_override=root / relative_root,
    )
    if violations or served is None:
        raise ValidationFailedError(
            message="; ".join(f"{source.id}: {v.path}: {v.rule}" for v in violations),
            violations=violations,
        )
    return served
