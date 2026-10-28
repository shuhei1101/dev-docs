---
name: global-setup
description: 端末ごとに 1 回、dev-docs のクローン・依存・端末の設定・Claude Code の env・起動を用意する。入れ直し・端末の移行・dev-docs の更新のあとにも使う
argument-hint: "[クローンのパス]"
---

# global-setup

`$ARGUMENTS` は dev-docs のクローンのパス。省くと聞く。
質問は AskUserQuestion で、既定値を推奨の選択肢にして聞く。

## 手順

1. 端末の設定のパスを決める。
   - 環境変数 `DEV_DOCS_CONFIG` があればその値、無ければ `~/.config/dev-docs/settings.yaml`
   - ファイルがあるかを確かめる

2. 端末の設定がある場合、バージョンを確かめる。
   - `{clone}/.venv/bin/python -m dev_docs migrate --plan` を実行する（`clone` は端末の設定の値）
   - 終了コード 6（設定が新しい）の場合、設定のバージョンと dev-docs のバージョンを示し、管理の MCP の `update` で dev-docs を更新するよう案内して止まる。端末の設定も env も書き換えない
   - 標準出力が空の場合、手順 3 へ進む
   - 標準出力に手順がある場合、手順を示す。`[destructive]` の行があるときは、当ててよいかを聞き、断られたら止まる
   - 当てる場合、`{clone}/.venv/bin/python -m dev_docs migrate`（破壊的な手順を許したときは `--allow-destructive` を付ける）を実行し、当てた手順とバックアップのパスを示す
   - スキーマの検証で足りないキーがあれば、そのキーだけを聞いて書き足す。`sources` の行とほかのキーは変えない

3. 端末の設定が無い場合、端末の設定を作る。
   - 端末の設定の場所を聞く（既定は `~/.config/dev-docs/settings.yaml`）
   - `$ARGUMENTS` が空ならクローンの場所を聞く
   - クローンが無ければ `git clone https://github.com/shuhei1101/dev-docs {クローンのパス}` を実行する
   - クローンで `uv sync` を実行して依存を入れる
   - `{クローン}/templates/settings.yaml` を元に、`clone` をクローンの絶対パスにした端末の設定を作る。`sources` は空にする

4. 端末の設定の場所が既定と違う場合、Claude Code の設定の env に `DEV_DOCS_CONFIG` を書く。
   - 書き先は `${CLAUDE_CONFIG_DIR:-~/.claude}/settings.json` の `env`
   - `env` のほかのキーと、ファイルのほかの内容は変えない

5. dev-docs を起動して、つながることを確かめる。
   - 待ち受けていなければ、`{clone}/.venv/bin/python -m dev_docs serve` を切り離して起動する。環境変数 `DEV_DOCS_CONFIG` に端末の設定のパスを渡す
   - `http://127.0.0.1:${DEV_DOCS_PORT:-8781}/mcp` にツールの一覧（`tools/list`）を要求し、文書の MCP のツールが 6 つ返ることを確かめる

6. 結果を示す。
   - 作ったもの（端末の設定のパス・env に書いたキー）と、つながった結果を出す
   - このセッションで文書の MCP を使うには `/mcp` でつなぎ直すことを案内する
   - 配信元を登録する `/dev-docs:setup` を案内する
