"""dev-docs コマンドの入口。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from importlib.metadata import version

PROG = "dev-docs"
DIST_NAME = "dev-docs"


def build_parser() -> argparse.ArgumentParser:
    """`--version` とサブコマンドの登録先を持つ引数の解析器を作る。"""
    parser = argparse.ArgumentParser(prog=PROG)
    # バージョンは配布のメタデータから引く（配布が入っていなければ PackageNotFoundError を伝える）
    parser.add_argument("--version", action="version", version=f"{PROG} {version(DIST_NAME)}")
    # 各サブコマンドは handler を既定値に持つ
    parser.add_subparsers(dest="cmd", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """引数を解析し、選ばれたサブコマンドの処理を呼んで終了コードを返す。"""
    # --version・--help・サブコマンドの誤りは、解析の中で SystemExit になる
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
