"""dev-docs コマンドの入口。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from importlib.metadata import version

from dev_docs import DIST_NAME
from dev_docs.features.prompt_doc.cli import run_prompt_doc
from dev_docs.main import run_files, run_migrate, run_serve

PROG = "dev-docs"


def build_parser() -> argparse.ArgumentParser:
    """`--version` とサブコマンドの登録先を持つ引数の解析器を作る。"""
    parser = argparse.ArgumentParser(prog=PROG)
    # バージョンは配布のメタデータから引く（配布が入っていなければ PackageNotFoundError を伝える）
    parser.add_argument("--version", action="version", version=f"{PROG} {version(DIST_NAME)}")
    # 各サブコマンドは handler を既定値に持つ
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    serve = subparsers.add_parser("serve", help="開発ドキュメントサーバーを起動する")
    serve.set_defaults(handler=run_serve)
    migrate = subparsers.add_parser("migrate", help="設定のバージョンを今のバージョンに移し替える")
    # --plan は書き換えず手順だけを出し、--record は手順を当てずにバージョンだけを書き換える
    mode = migrate.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="当てる手順を出して終わる")
    mode.add_argument("--record", action="store_true", help="version だけを今のバージョンにする")
    migrate.add_argument(
        "--source", default=None, help="移し替える配信元の dev-docs.yaml（省くと端末の設定）"
    )
    migrate.add_argument(
        "--allow-destructive", action="store_true", help="キーの削除など値を捨てる手順も当てる"
    )
    migrate.set_defaults(handler=run_migrate)
    files = subparsers.add_parser("files", help="管理用の YAML に載せるファイルの一覧を出す")
    files.add_argument("--root", required=True, help="配信元のフォルダ")
    files.add_argument(
        "--paths", required=True, action="append", help="範囲の glob（--root からの相対）"
    )
    files.add_argument("--exclude", action="append", default=[], help="外すファイル名の glob")
    files.set_defaults(handler=run_files)
    prompt_doc = subparsers.add_parser(
        "prompt-doc", help="標準入力のプロンプトの YAML を Markdown にして標準出力に出す"
    )
    prompt_doc.set_defaults(handler=run_prompt_doc)
    return parser


def main(argv: list[str] | None = None) -> int:
    """引数を解析し、選ばれたサブコマンドの処理を呼んで終了コードを返す。"""
    # --version・--help・サブコマンドの誤りは、解析の中で SystemExit になる
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
