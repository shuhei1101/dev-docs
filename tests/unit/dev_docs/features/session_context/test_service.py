from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dev_docs.features.access.types import SourceAccess
from dev_docs.features.documents.types import Document
from dev_docs.features.seen.types import SessionKey
from dev_docs.features.session_context.service import (
    _collect_warnings,
    _context_text,
    build_session_context,
)
from dev_docs.features.session_context.types import (
    CONTEXT_MAX_CHARS,
    SESSION_USAGE,
    SETUP_GUIDE,
    SessionContextRequest,
)
from dev_docs.features.settings.types import SourceEntry, SourceScope, TerminalConfig
from dev_docs.main import Handlers, build_handlers

MISSING_FILES_CONFIG = (
    "name: a\n"
    'version: "0"\n'
    "documents:\n"
    "  - id: src\n"
    "    type: yaml\n"
    "    paths: [src/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)
BROKEN_CONFIG = "name: b\ndocuments:\n  - id: rules\n    type: yaml\n"


def _access(source_id: str, access: str = "write", description: str = "") -> SourceAccess:
    """使える配信元の 1 行を作る。"""
    return SourceAccess(
        source_id=source_id,
        access=access,  # type: ignore[arg-type]
        current=False,
        description=description,
    )


def _two_sources(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> tuple[Handlers, Path]:
    """書ける sample（管理用の YAML に無いファイル 1 件）と、読める notes の配線済みの関数を作る。"""
    sample = make_source_dir("sample", unindexed=1)
    notes = make_source_dir("notes")
    handlers = build_handlers(
        make_terminal_config(
            sources=[
                make_entry(str(sample), source_id="sample"),
                make_entry(
                    str(notes), source_id="notes", scope=SourceScope(read=[str(sample.parent)])
                ),
            ]
        )
    )
    return handlers, sample.parent


def test_build_session_context(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """使える配信元・使い方・警告を返す（正常系）。"""
    # 準備
    handlers, cwd = _two_sources(make_source_dir, make_terminal_config, make_entry)
    request = SessionContextRequest(cwd=str(cwd), reason="startup")
    # 実行
    result = build_session_context(request, handlers=handlers)
    # 検証
    assert {item.id: item.access for item in result.sources} == {
        "sample": "read_write",
        "notes": "read",
    }
    assert SESSION_USAGE in result.context
    assert len(result.warnings) == 1
    assert result.forgotten is False


def test_build_session_context_when_cleared(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_document: Callable[..., Document],
) -> None:
    """/clear の後は返し済みの記録を削除する（正常系）。"""
    # 準備
    handlers, cwd = _two_sources(make_source_dir, make_terminal_config, make_entry)
    key = SessionKey("s1", "")
    handlers.seen.mark_returned(key, "sample", "body", [make_document()])
    request = SessionContextRequest(cwd=str(cwd), session_id="s1", reason="clear")
    # 実行
    result = build_session_context(request, handlers=handlers)
    # 検証
    assert result.forgotten is True
    assert handlers.seen.last_read(key, "sample") == {}


def test_build_session_context_when_resumed(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
    make_document: Callable[..., Document],
) -> None:
    """再開では記録を削除しない（正常系）。"""
    # 準備
    handlers, cwd = _two_sources(make_source_dir, make_terminal_config, make_entry)
    key = SessionKey("s1", "")
    handlers.seen.mark_returned(key, "sample", "body", [make_document()])
    request = SessionContextRequest(cwd=str(cwd), session_id="s1", reason="resume")
    # 実行
    result = build_session_context(request, handlers=handlers)
    # 検証
    assert result.forgotten is False
    assert list(handlers.seen.last_read(key, "sample")) == ["doc-1"]


def test_build_session_context_when_no_source_available(
    tmp_path: Path,
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """使える配信元が無い（正常系）。"""
    # 準備
    handlers, _ = _two_sources(make_source_dir, make_terminal_config, make_entry)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    request = SessionContextRequest(cwd=str(elsewhere), reason="startup")
    # 実行
    result = build_session_context(request, handlers=handlers)
    # 検証
    assert result.sources == []
    assert result.context == SETUP_GUIDE


def test_collect_warnings(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """同期のずれ・古い設定・配信していない配信元を並べる（正常系）。"""
    # 準備
    write_files(
        tmp_path / "a",
        {
            "dev-docs.yaml": MISSING_FILES_CONFIG,
            "schemas/files.schema.yaml": "title: file\ntype: object\n",
            "src/files.yaml": "files:\n  - path: x.py\n  - path: y.py\n",
        },
    )
    write_files(tmp_path / "b", {"dev-docs.yaml": BROKEN_CONFIG})
    handlers = build_handlers(
        make_terminal_config(
            sources=[
                make_entry(str(tmp_path / "a" / "dev-docs.yaml"), source_id="a"),
                make_entry(str(tmp_path / "b" / "dev-docs.yaml"), source_id="b"),
            ]
        )
    )
    # 実行
    result = _collect_warnings([_access("a")], handlers=handlers)
    # 検証
    assert len(result) == 3
    assert result[0].startswith("a: ")
    assert "2 件" in result[0]
    assert "check_project" in result[0]
    assert result[1].startswith("a: 設定のバージョンが古い")
    assert result[2].startswith("b: 配信していません")


def test_collect_warnings_when_unavailable_source(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """使えない配信元の同期のずれは載せない（正常系）。"""
    # 準備
    handlers = build_handlers(
        make_terminal_config(
            sources=[make_entry(str(make_source_dir("a", unindexed=1)), source_id="a")]
        )
    )
    # 実行
    result = _collect_warnings([], handlers=handlers)
    # 検証
    assert result == []


def test_context_text() -> None:
    """配信元の行・使い方・警告をつなぐ（正常系）。"""
    # 準備
    available = [_access("a", "write", "A の説明"), _access("b", "read", "B の説明")]
    # 実行
    result = _context_text(available, ["警告です"])
    # 検証
    positions = [
        result.index("- a（読み書き）: A の説明"),
        result.index("- b（読み取りだけ）: B の説明"),
        result.index(SESSION_USAGE),
        result.index("注意:"),
        result.index("- 警告です"),
    ]
    assert result.startswith("dev-docs の文書の MCP（dev-docs）で、次の配信元を使えます。")
    assert positions == sorted(positions)


def test_context_text_when_too_long() -> None:
    """上限を超えるときは説明を省き、行を切る（正常系）。"""
    # 準備
    description = "説明" * 250
    available = [_access(f"s{index:03d}", "write", description) for index in range(100)]
    # 実行
    result = _context_text(available, [])
    # 検証
    assert len(result) <= CONTEXT_MAX_CHARS
    assert "説明説明説明" not in result
    assert "- ほか " in result
