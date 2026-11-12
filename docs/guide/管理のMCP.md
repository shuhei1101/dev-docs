# 管理のMCP

管理の MCP の 3 つのツールの引数・返す内容・エラーの一覧

## 共通

接続先は `http://127.0.0.1:${DEV_DOCS_PORT:-8781}/_admin/mcp` で、トランスポートは HTTP（Streamable HTTP）です。
`127.0.0.1` だけで待ち受け、作業場所（`cwd`）での絞り込みは持たず、全ての配信元を扱います。
配信元の読み直し・検査・試しの変換・`nav` の書き込みは、[project-index](https://github.com/shuhei1101/project-index) の管理の MCP のツールです。

<!-- table: data -->

| ツール | 種類 | 役割 |
| --- | --- | --- |
| `status` | 読み取り | 待ち受け・バージョン・端末の設定・project-index への接続・配信元ごとの状態 |
| `restart` | 書き込み | サーバーの再起動 |
| `update` | 書き込み | dev-docs のクローンの更新と、必要なら再起動 |

<!-- /table -->

`status` には `readOnlyHint: true` が付きます。
タイムアウトは設けません。`status` の project-index への問い合わせは 45 秒で打ち切ります。

`status` は引数 `format`（`markdown` か `json`、既定 `markdown`）を持ちます。
`json` のときは、同じ中身を structuredContent と text に入れます。

### バージョンの比較

| 値 | 意味 |
| --- | --- |
| `current` | 設定の `version` が dev-docs が読めるバージョンと同じ |
| `old` | 古い。`dev-docs migrate` で移し替える |
| `newer` | 新しい。dev-docs を更新する |

## status

待ち受けのアドレス・dev-docs のバージョン・端末の設定・project-index への接続と、project-index から取得した配信元ごとの状態を返します。

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `format` | `markdown` / `json` | `markdown` | 返す形式 |

<!-- table: data -->

| 返すフィールド | 型 | 説明 |
| --- | --- | --- |
| `address` | str | 待ち受けている URL |
| `version` | str | 動いている dev-docs のバージョン |
| `pid` | int | サーバーのプロセス ID |
| `terminal.file` | str | 読んだ端末の設定のパス |
| `terminal.version_state` | `current` / `old` / `newer` | 端末の設定の `version` の比較 |
| `sources[].id` | str | 配信元の ID |
| `project_index.address` | str | 端末の設定の `project_index` |
| `project_index.reachable` | bool | project-index の読み取り API が応答したか |
| `project_index.error` | str / null | つながらなかった理由。`reachable` が `false` のとき |
| `sources[].status` | `serving` / `not_served` / `disabled` | project-index が返した状態。配信中・検証で外した・`enabled: false` |
| `sources[].errors[]` | list[str] | project-index が返した配信しない理由（`{キーのパス}: {理由}`）。`not_served` のとき |
| `leftover_sources` | list[str] | 端末の設定に前のバージョンから残った `sources` の行の ID |

<!-- /table -->

```markdown
http://127.0.0.1:8781/ dev-docs 0.3.0（pid 4242）
端末の設定: /home/u/.config/dev-docs/settings.yaml（current）
project-index: http://127.0.0.1:8786（つながっている）
| source | 状態 |
| --- | --- |
| sample | serving |
| broken | not_served（documents[0].paths: 必須のキーが無い） |
```

配信元が 0 件のときは、空の一覧を返します。
配信元の状態は呼ばれるたびに project-index から取得し、dev-docs の中に控えません。
project-index につながらないときもエラーにせず、`reachable` を `false`、`sources[]` を空にして返します。

## restart

応答を返してからサーバーを止め、同じプロセス ID・同じ環境変数で `dev-docs serve` を起動し直します。
`/_admin/mcp` の接続は切れるので、つなぎ直します。
起動し直したプロセスは、project-index に問い合わせる前に待ち受けを始めます。
再起動の結果は、つなぎ直した後の `status` で確かめます。

処理中の要求は、project-index への問い合わせの制限時間（45 秒）の 1.5 倍を上限に待ちます。
過ぎたら残りの要求を切って止めます。
起動に失敗したときは、`dev-docs serve` の終了コードで止まり、次のセッションの SessionStart のフックが起動し直します。

引数はありません。

| 返すフィールド | 型 | 説明 |
| --- | --- | --- |
| `pid` | int | 起動し直した後も変わらないプロセス ID |
| `restarting` | bool | 常に `true` |

| エラー | 発生条件 |
| --- | --- |
| `RestartInProgressError` | 前の `restart`・`update` の再起動がまだ終わっていない |

## update

端末の設定の `clone` で `git pull --ff-only` と `uv sync` を実行し、端末の設定の移し替えが要らなければ起動し直します。
新しいバージョンのコードで `{clone}/.venv/bin/python -m dev_docs migrate --plan` を実行し、当てる手順があれば移し替えが要るとします。
`git pull`・`uv sync`・`migrate --plan` は、それぞれ 300 秒で打ち切ります。

引数はありません。

| 返すフィールド | 型 | 説明 |
| --- | --- | --- |
| `previous_version` | str | 更新する前の dev-docs のバージョン |
| `version` | str | 更新した後のクローンのバージョン。`updated: false` のときは `previous_version` と同じ |
| `updated` | bool | 新しい commit を取り込んだか |
| `migration_needed` | bool | 端末の設定の移し替えが要るか。`true` のときは再起動しない |
| `restarting` | bool | 応答の後に起動し直すか |

`migration_needed: true` のときは、`dev-docs migrate` を実行してから `restart` を呼びます。
project-index への接続と配信元の状態は、起動し直した後の `status` で確かめます。

| エラー | 発生条件 |
| --- | --- |
| `UpdateFailedError` | `git pull --ff-only`・`uv sync`・`migrate --plan` が 0 以外で終わった、または打ち切った。失敗したコマンドと標準エラーを返し、再起動しない。クローンに commit していない変更があるときも、変更に触らずこのエラーを返す |
| `RestartInProgressError` | 再起動か更新がまだ終わっていない |

手順は [dev-docsを更新する](./dev-docsを更新する.md) にあります。
