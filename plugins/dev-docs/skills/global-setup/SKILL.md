---
name: global-setup
description: 端末ごとに 1 回、画面を表示する dev-docs のクローン・依存・端末の設定・Claude Code の env・起動を用意する。再インストール・端末の移行・dev-docs の更新のあとにも使用する。文書の MCP（検索・書き込み）は project-index の用意に案内する
argument-hint: "[クローンのパス]"
---

# global-setup

`$ARGUMENTS` は dev-docs のクローンのパス。省くと聞く。
文書の MCP（検索・書き込み）と配信元の登録は project-index が持つ。project-index を入れていなければ、先に project-index の `global-setup` を案内する。
質問は AskUserQuestion で、既定値を推奨の選択肢にして聞く。

## 手順

1. 端末の設定のパスを決める。
   - 環境変数 `DEV_DOCS_CONFIG` があればその値、無ければ `${XDG_CONFIG_HOME:-~/.config}/dev-docs/settings.yaml`（`XDG_CONFIG_HOME` が空の文字列か相対パスなら `~/.config/dev-docs/settings.yaml`）
   - ファイルがあるかを確認する

2. 端末の設定がある場合、バージョンを確認する。
   - `{clone}/.venv/bin/python -m dev_docs migrate --plan` を実行する（`clone` は端末の設定の値。端末の設定に `clone` が無いときは `$ARGUMENTS`、空ならクローンの場所を聞いた値。聞いた値は、スキーマの検証で足りないキーを追加するときに再度聞かずに記載する）
   - 終了コード 6（設定が新しい）の場合、設定のバージョンと dev-docs のバージョンを示し、管理の MCP の `update` で dev-docs を更新するよう案内して止まる。端末の設定も env も書き換えない
   - 標準出力が空の場合、手順 3 へ進む
   - 標準出力に手順がある場合、手順を示す。`[destructive]` の行があるときは、適用してよいかを聞き、断られたら止まる
   - 適用する場合、`{clone}/.venv/bin/python -m dev_docs migrate`（破壊的な手順を許したときは `--allow-destructive` を付ける）を実行し、適用した手順とバックアップのパスを示す
   - `sources` を project-index へ移す手順（`export_sources`）がある場合、`--project-index` に project-index のアドレス（既定 `http://127.0.0.1:8786`）を指定する。終了コード 7 のときは、project-index を起動してからやり直すよう案内して止まる
   - スキーマの検証で足りないキーがあれば、そのキーだけを聞いて追加する。ほかのキーは変えない

3. 端末の設定が無い場合、端末の設定を作る。
   - 端末の設定の場所を聞く（既定は `${XDG_CONFIG_HOME:-~/.config}/dev-docs/settings.yaml`）
   - `$ARGUMENTS` が空ならクローンの場所を聞く
   - クローンが無ければ `git clone https://github.com/shuhei1101/dev-docs {クローンのパス}` を実行する
   - クローンで `uv sync` を実行して依存を入れる
   - `{クローン}/templates/settings.yaml` を元に、`clone` をクローンの絶対パス、`project_index` を project-index のアドレス（既定 `http://127.0.0.1:8786`）にした端末の設定を作る

4. 端末の設定の場所が既定と違う場合、Claude Code の設定の env に `DEV_DOCS_CONFIG` を記載する。
   - 記載先は `${CLAUDE_CONFIG_DIR:-~/.claude}/settings.json` の `env`
   - `env` のほかのキーと、ファイルのほかの内容は変えない

5. dev-docs を起動して、つながることを確認する。
   - unit の名前は環境変数 `DEV_DOCS_UNIT`（無ければ `dev-docs.service`）。空の文字列なら unit を使用しない
   - unit を使用し、`systemctl --user show-environment` が終了コード 0 なら、`${XDG_CONFIG_HOME:-~/.config}/systemd/user/{unit の名前}` に unit を書く
     - 同じ名前の unit があるときは、同じフォルダの `{unit の名前}.bak-{yyyymmddHHMMSS}` へ退避してから書き換える
     - `[Service]` に `WorkingDirectory={clone}`・`ExecStart={clone}/.venv/bin/python -m dev_docs serve`・`Environment=DEV_DOCS_CONFIG={端末の設定のパス}`（`DEV_DOCS_PORT` があれば `Environment=DEV_DOCS_PORT={値}` も）・`Restart=on-failure`・`RestartPreventExitStatus=3` を書き、`[Install]` に `WantedBy=default.target` を書く
     - `systemctl --user daemon-reload` と `systemctl --user enable --now {unit の名前}` を実行する。既に動いていれば `systemctl --user restart {unit の名前}` を実行する
     - `systemctl --user show -p MainPID --value {unit の名前}` と、`127.0.0.1:${DEV_DOCS_PORT:-8781}` を待ち受けるプロセスの pid（`ss -ltnpH 'sport = :{ポート}'` で調べる）を照合する
     - 一致しない（unit が終了コード 3 で止まった）ときは、ポートを持つプロセスの pid とコマンドラインを示し、そのプロセスを止めるかを AskUserQuestion で利用者に確認する
       - 止めると答えたら、そのプロセスを止めてから `systemctl --user start {unit の名前}` を実行し、照合し直す
       - 止めないと答えたら、ポートを持つプロセスの pid と、そのプロセスを止めてから `systemctl --user start {unit の名前}` を実行する案内を結果に出す
   - unit を使用しないか systemd --user を使用できず、待ち受けていなければ、`{clone}/.venv/bin/python -m dev_docs serve` を切り離して起動する。環境変数 `DEV_DOCS_CONFIG` に端末の設定のパスを指定する
   - `http://127.0.0.1:${DEV_DOCS_PORT:-8781}/_admin/mcp` の `status` を呼び、project-index につながっていることを確認する

6. 結果を示す。
   - 作ったもの（端末の設定のパス・env に記載したキー・unit の名前とファイルのパス）と、つながった結果を出す
   - このセッションで管理の MCP を使用するには `/mcp` で再接続することを案内する
   - 配信元の登録は project-index のスキル `setup` か、dev-docs の設定画面の「配信元を追加」で行うことを案内する
