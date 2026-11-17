# dev-docsを更新する

update と dev-docs migrate で dev-docs を更新し、端末の設定を移し替える手順

画面の側（dev-docs）と索引の側（project-index）は別々に更新します。
project-index の更新は [project-indexを更新する](https://github.com/shuhei1101/project-index/blob/develop/docs/guide/project-index%E3%82%92%E6%9B%B4%E6%96%B0%E3%81%99%E3%82%8B.md) にあります。

## 手順

<!-- steps -->

1. 管理の MCP の `update` を呼ぶ。
   クローンで `git pull --ff-only` と `uv sync` を実行し、新しいバージョンのコードで `dev-docs migrate --plan` を実行して移し替えの要否を確認する。
2. 応答の `updated`・`migration_needed`・`restarting` で次の動きを決める（下の表）。
3. 再起動したら、`/mcp` で再接続する。
4. 管理の MCP の `status` で、新しいバージョンと、project-index につながって配信元が `serving` であることを確認する。

<!-- /steps -->

| 応答 | 動き |
| --- | --- |
| `updated: false` | 新しい commit が無い。何も変えず、再起動もしない |
| `migration_needed: false` | 応答を返却した後に自動で再起動する |
| `migration_needed: true` | 再起動しない。次の「端末の設定を移し替える」へ進む |

## 端末の設定を移し替える

`update` が `migration_needed: true` を返却したときの手順です。
新しいバージョンが端末の設定の記載方法を変えているので、移し替えてから再起動します。

<!-- steps -->

1. 適用する手順を確認する。
   端末の設定は書き換わらない。
   ```bash
   dev-docs migrate --plan
   ```
2. 手順を適用する。
   適用する前に、同じフォルダへ `{ファイル名}.bak-{時刻}` のバックアップを取る。
   ```bash
   dev-docs migrate
   ```
3. 管理の MCP の `restart` を呼ぶ。
4. `/mcp` で再接続、`status` で新しいバージョンと配信元を確認する。

<!-- /steps -->

手で移し替えた設定は、`--record` で `version` だけを今のバージョンに書き換えます。
オプションと終了コードは [CLI](./CLI.md) にあります。

## 今の端末から移る

文書の MCP と配信元の読み込みを dev-docs が持っていた端末（端末の設定の `version: "1"`）から、project-index を使用する形へ移る手順です。
文書の MCP を使用できない期間を作らないよう、project-index を先に入れてから dev-docs を更新します。

<!-- steps -->

1. project-index を入れ、待ち受けていることを確認する（[project-indexを入れる](https://github.com/shuhei1101/project-index/blob/develop/docs/guide/project-index%E3%82%92%E5%85%A5%E3%82%8C%E3%82%8B.md)）。
2. 管理の MCP の `update` を呼ぶ。`migration_needed: true` が返る。
3. 適用する手順を確認する。`2: ` で始まる `sources` を project-index へ移す手順が出る。
   ```bash
   dev-docs migrate --plan
   ```
4. 手順を適用する。端末の設定の `sources` の行を project-index の端末の設定へ 1 行ずつ追加し、`project_index` を追記する。
   ```bash
   dev-docs migrate --project-index http://127.0.0.1:8786
   ```
5. 標準出力に移さなかった行（project-index に同じ id で内容の違う行がある）が出たら、project-index で行を修正してから、端末の設定の `sources` に残った行を削除する。
6. 管理の MCP の `restart` を呼び、`/mcp` で再接続する。
7. Claude Code の `/mcp` で、文書の MCP が project-index の接続先につながっていることを確認する。

<!-- /steps -->

配信元の設定（`dev-docs.yaml`）の移し替えと、`project-index.yaml` への改名は project-index で行います（[project-indexを更新する](https://github.com/shuhei1101/project-index/blob/develop/docs/guide/project-index%E3%82%92%E6%9B%B4%E6%96%B0%E3%81%99%E3%82%8B.md)）。

## 失敗したとき

<!-- table: {"kind": "data"} -->

| 事象 | 動き |
| --- | --- |
| `git pull --ff-only` が失敗する（fast-forward できない・commit していない変更がある） | `update` が失敗したコマンドと標準エラーを返却する。クローンに触らず、再起動もしない |
| `uv sync` が失敗する | `update` が失敗したコマンドと標準エラーを返却し、再起動しない |
| 移し替えの手順が失敗する、または適用した結果がスキーマに違反する | 端末の設定を書き換えず、失敗した手順と理由を標準エラーに出す |
| 適用する手順に破壊的なもの（キーの削除）がある | 触らずに止まる。内容を確認し、了承できれば `--allow-destructive` を付けて実行する |
| 端末の設定の `version` が dev-docs より新しい | 触らずに止まる。`update` で dev-docs を更新する |
| `sources` を移す先の project-index につながらない | 端末の設定を書き換えずに終了コード 7 で止まる。project-index を起動してから再実行する |
| `restart`・`update` の再起動が終わる前に呼んだ | `RestartInProgressError` で断る。再起動した後に再度呼び出す |

<!-- /table -->

起動に失敗したときは、次のセッションの SessionStart のフックが再起動します。
