"""dev-docs コマンドの入口。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from importlib.metadata import version

from dev_docs import DIST_NAME
from dev_docs.main import run_migrate, run_serve

PROG = "dev-docs"


def build_parser() -> argparse.ArgumentParser:
    """`--version` とサブコマンドの登録先を持つ引数の解析器を作る。"""
    parser = argparse.ArgumentParser(prog=PROG)
    # バージョンは配布のメタデータから取得する（配布がインストールされていなければ PackageNotFoundError を伝える）
    parser.add_argument("--version", action="version", version=f"{PROG} {version(DIST_NAME)}")
    # 各サブコマンドは handler を既定値に持つ
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    serve = subparsers.add_parser("serve", help="開発ドキュメントサーバーを起動する")
    serve.set_defaults(handler=run_serve)
    migrate = subparsers.add_parser("migrate", help="設定のバージョンを今のバージョンに移し替える")
    # --plan は書き換えず手順だけを出し、--record は手順を当てずにバージョンだけを書き換える
    mode = migrate.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="適用する手順を出して終わる")
    mode.add_argument("--record", action="store_true", help="version だけを今のバージョンにする")
    migrate.add_argument(
        "--project-index", default=None, help="sources を移す先の project-index のアドレス"
    )
    migrate.add_argument(
        "--allow-destructive", action="store_true", help="キーの削除など値を捨てる手順も適用する"
    )
    migrate.set_defaults(handler=run_migrate)
    return parser


def main(argv: list[str] | None = None) -> int:
    """引数を解析し、選ばれたサブコマンドの処理を呼んで終了コードを返却する。"""
    # --version・--help・サブコマンドの誤りは、解析の中で SystemExit になる
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
