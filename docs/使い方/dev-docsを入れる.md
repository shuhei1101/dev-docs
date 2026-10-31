# dev-docsを入れる

プラグインを入れ、global-setup で端末の設定と起動を用意して、/mcp につなぐ手順

## 前提

- 端末に uv・git・Claude Code がある
- dev-docs のリポジトリをクローンしてある（`/dev-docs:global-setup` の引数に渡すパス）

## 手順

<!-- steps -->

1. dev-docs のリポジトリをマーケットプレイスとして追加する。
   ```text
   /plugin marketplace add shuhei1101/dev-docs
   ```
2. プラグイン `dev-docs` をユーザースコープで入れる。
   ```text
   /plugin install dev-docs@dev-docs
   ```
   インストールの範囲を聞かれたら、ユーザースコープを選ぶ。
3. `/dev-docs:global-setup` を実行する。
   引数に dev-docs のクローンのパスを渡す。省くと聞かれる。
   ```text
   /dev-docs:global-setup /home/me/repo/dev-docs
   ```
4. 聞かれた端末の設定の場所に答える。
   既定は `~/.config/dev-docs/settings.yaml`。
5. スキルの最後の応答にある、作った端末の設定のパスと接続の結果を確かめる。
6. Claude Code で `/mcp` を開き、`dev-docs` につなぎ直す。
7. 配信元を登録する。
   手順は [配信元を配信する](./配信元を配信する.md) の「スキルで登録する」にある。

<!-- /steps -->

## global-setup が用意するもの

| 対象 | 内容 |
| --- | --- |
| 依存 | クローンで `uv sync` を実行する |
| 端末の設定 | 雛形から作る。`version` に dev-docs のバージョン、`clone` に引数のパス、`sources: []` を持つ |
| Claude Code の env | 端末の設定が既定の場所と違うときだけ、`settings.json` の env に `DEV_DOCS_CONFIG` を記載する。env のほかのキーは変えない |
| 起動 | `dev-docs serve` を切り離して起動する |
| 接続の確認 | `/mcp` につながり、文書の MCP のツールが 7 つ返ることを確かめる |

## つなぎ直す理由

スキルが起動したサーバーには、そのセッションの MCP の接続が間に合いません。
`/mcp` でつなぎ直すと、そのセッションから使えます。
次のセッションからは、プラグインのフックが落ちているサーバーを起動するので、つなぎ直しは要りません。
フックの動きは [管理用プラグイン](../はじめに/コアコンセプト/管理用プラグイン.md) にあります。

## 2 回目以降

入れ直し・端末の移行・dev-docs の更新のあとも、同じ `/dev-docs:global-setup` を実行します。
端末の設定がある場合は、`version` を dev-docs のバージョンと比べて進め方を決めます。
既にある `sources[]` の行は消えません。

| 比べた結果 | 動き |
| --- | --- |
| 同じ | スキーマで検証し、足りないキーだけを聞いて記載する。端末の設定の場所は聞かない |
| 古い | `dev-docs migrate --plan` で当てる手順を示し、了承されたら `dev-docs migrate` で移し替える。当てる前にバックアップを取る |
| 新しい | 端末の設定も env も書き換えず、管理の MCP の `update` で dev-docs を更新するよう案内して止まる |

移し替えの詳細は [dev-docsを更新する](./dev-docsを更新する.md) にあります。
