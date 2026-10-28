---
name: setup
description: フォルダを dev-docs の配信元として端末の設定に登録する。2 回目以降は、範囲のファイルと管理用の YAML を突き合わせて追加・削除・改名を直す
argument-hint: "[path]"
---

# setup

`$ARGUMENTS` は配信元のフォルダ。省くと今の作業場所。
質問は AskUserQuestion で、既定値を推奨の選択肢にして聞く。
管理の MCP のツール（`check_project`・`reload`）は `mcp__plugin_dev-docs_dev-docs-admin__` で始まる名前、`write_docs` は文書の MCP（`mcp__plugin_dev-docs_dev-docs__write_docs`）にある。

## 手順

1. 端末の設定を確かめる。
   - 端末の設定が無ければ、`/dev-docs:global-setup` を案内して止まる

2. 配信元の設定を決める。
   - `{path}/dev-docs.yaml` がある場合、`check_project` を呼ぶ。`version_state` が `old` なら、`dev-docs migrate --source {path}/dev-docs.yaml --plan` で手順を示し、了承されたら `dev-docs migrate --source ...` で当てる。`newer` なら、管理の MCP の `update` で dev-docs を更新するよう案内して止まる。違反があれば、キーのパスと理由を示して止まる。端末の設定は書き換えない
   - `{path}/dev-docs.yaml` が無い場合、手順 3 以降で `{dev-docs のクローン}/templates/dev-docs.yaml` から作る（YAML でない範囲の配信元）

3. 権限と範囲を聞く。端末の設定の `sources[]` に同じ配信元の行が既にあるときは、今の値を示して変えるかだけを聞く。

   | 質問 | 既定 |
   | --- | --- |
   | 書き込める作業場所（`scope.write`）。パスか glob | `{path}` |
   | 読める作業場所（`scope.read`） | `{path}/**` |
   | 検索できるようにするファイル（`documents[].paths`）。`dev-docs.yaml` が無いときだけ聞く | `**/*.md`。`.git`・`node_modules`・`.claude/worktrees` の下は除く |

4. YAML でない範囲を管理用の YAML の行にする。
   - 範囲のファイルを集め、管理用の YAML（`files.yaml`）の行と突き合わせる
   - 結果は次の候補にする

     | 突き合わせの結果 | 候補 |
     | --- | --- |
     | 管理用の YAML に無いファイル | 仮のメタデータを付けて行を追加 |
     | ファイルが無い行 | 行を削除 |
     | 名前が変わったファイル | 行のパスを新しくし、メタデータは残す。Git の配信元は `git diff --name-status -M` のリネームの検出、Git 管理外は内容のハッシュの一致で見つける |

   - 仮のメタデータは、見出しと冒頭から `name` と `description` を付ける。`tags` は付けるタグがあるときだけ付ける。管理用の YAML の行が既にメタデータを持つファイルには付けない
   - 追加・削除・改名と仮のメタデータを表で示し、書いてよいかを聞く。断られたら何も書き換えずに止まる

5. 確認が済んだものを書く。
   - `dev-docs.yaml` が無い場合、`{クローン}/templates/dev-docs.yaml` から `dev-docs.yaml` を作り、`name`・`description`・`documents[].paths` を決めた値にする。`{クローン}/templates/files.schema.yaml` を `{path}/schemas/files.schema.yaml` にコピーする
   - 管理用の YAML の行は、`write_docs` で書く（配信元が登録済みのとき）。登録前の配信元は、`templates/files.schema.yaml` に沿って `files.yaml` を直接書く
   - `check_project`（`path` は配信元のフォルダ）を呼び、違反が無いことを確かめる。違反があれば示して止まり、端末の設定は書き換えない

6. 端末の設定の `sources[]` に行を書き、配信を始める。
   - 端末の設定の `sources[]` に、`config`（`{path}/dev-docs.yaml` の絶対パス）・`scope.write`・`scope.read` の行を書く。同じ配信元の行があれば、その行を直す
   - 管理の MCP の `reload` を呼ぶ。`/mcp` のセッションは切れない
   - 追加した配信元と `check_project` の結果（索引の同期の件数を含む）を示す

## 開発中の使い方

範囲のファイルを作った・消した・改名したときは、この手順を待たず、作業中のエージェントが管理用の YAML の行を `write_docs` で直す。
