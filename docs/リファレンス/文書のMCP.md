# 文書のMCP

6 つのツールの引数・既定値・上限・エラーの一覧

## 共通

接続先は `http://127.0.0.1:${DEV_DOCS_PORT:-8781}/mcp` の 1 つで、トランスポートは HTTP（Streamable HTTP）です。
ツールは全配信元で共通で、配信元は引数 `source` で指します。

| ツール | 種類 | 役割 |
| --- | --- | --- |
| `search_docs` | 読み取り | 検索・取得・一覧・件数・集計 |
| `write_docs` | 書き込み | 作成・部分更新・置き換え（一括） |
| `delete_docs` | 書き込み（`destructiveHint: true`） | 削除（一括） |
| `describe` | 読み取り | 使える配信元の一覧・説明書・種類・スキーマ |
| `list_changes` | 読み取り | 区間か前回読んだ時点からの変更 |
| `trace_related` | 読み取り | 関連のたどりと関連の候補 |

読み取りのツールには `readOnlyHint: true` が付き、並列に呼ばれます。
引数の検証は strict tool use を使わず、サーバーが配信元のスキーマで検証し、直し方を添えてエラーを返します。

### 共通の引数

<!-- table: data -->

| 引数 | 型 | 説明 | 補足 |
| --- | --- | --- | --- |
| `source` | str（`search_docs`・`list_changes` は list[str] も可） | 配信元の ID（端末の設定の `sources[].id`） | 省略すると作業中の配信元。`scope` に当たらない配信元はエラー。`search_docs`・`list_changes` は配列か `*`（読める全配信元）も受ける |
| `ref` | str | 読むリビジョン（ブランチ・コミット・タグ） | 省略すると配信元の `default_ref`。作業中の配信元は作業ツリー。Git 管理外の配信元と、複数の配信元を指したときは渡せない |
| `worktree` | str | 読み書きするワークツリーのパス | 配信元の `worktrees` に当たるパスだけ。省略して `cwd` がワークツリーの中なら、そのワークツリー |
| `format` | `markdown` / `json` | 返す形式 | 既定 `markdown` |
| `cwd` | str | 作業場所 | 管理用プラグインのフックが入れる。エージェントは指定しない |
| `session_id`・`agent_id` | str | 会話キー | 同じ。メインの会話は `agent_id` が空 |

<!-- /table -->

ツールの引数に無いキーは無視します。
`ref` を持つのは `search_docs` と `trace_related` で、`write_docs`・`delete_docs` は `ref` を持ちません。
`write_docs`・`delete_docs` は `format` によらず JSON を返します。

### 返す形式

| ツールの種類 | `markdown`（既定） | `json` |
| --- | --- | --- |
| 一覧・件数・集計 | Markdown の表。先頭に総件数 | 行の配列と総件数などを持つオブジェクト |
| 本文 | YAML が正本の文書は YAML のまま、Markdown の文書は Markdown。複数なら `<document>` で包む。包みに文書ごとの `path`・`scope` を付ける | 文書のオブジェクトの配列。各項目に `path`・`scope` |
| 差分 | git と同じ `+`・`-` の行。`view: full` は文書ごとに `<document>` で包み、`path`・`scope` を付ける | 変わったキーと前後の値。各項目に `path`・`scope` |
| 書き込み・削除 | JSON | JSON |

`markdown` のときは structuredContent を返しません。
`json` のときと書き込み・削除は、structuredContent と text に同じ JSON を入れます。

### 文書の場所と範囲

`search_docs`・`trace_related`・`list_changes` は、返した文書ごとに場所（`path`）と返した範囲（`scope`）を載せます。
`markdown` は `<document path="..." scope="...">` の属性、`json` は各項目の直下（`id`・`source` と同じ階層で `values` の外）の `path`・`scope` です。
rule-inject は、この `path` と `scope` で文書を既読にします。

`path` は、配信元（ワークツリーを指したときはワークツリー）の直下と文書のパスを結んだ絶対パスです。
`body_file` のある `records` の要素は、`body_file` が指すファイルのパスになります。
メタデータのキー `path`（`values` の中。管理用の YAML では `files[].path` の値）とは別の項目です。

<!-- table: data -->

| `scope` | 返したもの | 該当する呼び出し |
| --- | --- | --- |
| `full` | 本文を切らずに返した | `search_docs` の `view: full` で、`max_chars_per_field` に収まり、`snippets` を渡さなかったとき |
| `section` | 本文の一部を返した | `max_chars_per_field` で切った本文、`snippets`、`body_file` の無い `records` の要素、`list_changes` の `view: full` の差分 |
| `summary` | 本文を返さなかった | `view: summary`、`exclude_fields` で `body` を除いた `view: full`、`trace_related`、`list_changes` の `view: summary` |

<!-- /table -->

次の文書には `path`・`scope` を載せません。
`markdown` の `<document>` は属性の無い包みになり、`json` の項目は `path`・`scope` を持ちません。

- `ref` を渡して読んだ文書。既読は今のルールの本文を読んだことを表すため
- `list_changes` で `to` を渡したときの文書、`change` が `deleted` の文書
- 返し済みにした文書
- `view: ids`・`view: count` の結果と、読めない配信元の文書

### 1 セッション 1 回

サーバーは会話キー（`session_id`・`agent_id`）ごとに、返した文書の id とハッシュを記録します。
同じバージョンの本文と、`trace_related` の関連の相手の名前・概要文は、2 回目から `（この会話で返し済み）` だけを返します。
`repeat_seen: true` で取り直せます。
一覧の各行の概要文は、選ぶために使うので省きません。

### 作成日時・更新日時

メタデータの `created`・`updated` は次の順で決めます。

1. Git の履歴があれば、そのファイルの最初と最後のコミットの日時
2. 無ければ、文書のメタデータの `created`・`updated`。Git 管理外の配信元では `write_docs` が付ける
3. どちらも無ければ空。並べ替えでは末尾

### バージョン

文書の `version` は内容のハッシュ（短縮）です。
ファイルの更新日時か大きさが変わった文書は、次の呼び出しで読み直します。
`write_docs`・`delete_docs` の `expected_version` に、読んだときの `version` を渡します。

## search_docs

条件に当たる文書を、指定した項目・量・順で返します。
ID で絞れば取得、`view: summary` で一覧、`view: count` で件数、`group_by` で集計になります。

<!-- table: data -->

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `filter` | Group か Condition | 全件 | 条件の木。下の「条件」 |
| `view` | `ids` / `summary` / `full` / `count` | `summary` | `ids` は ID だけ、`summary` は共通のメタデータ、`full` は本文込み、`count` は件数だけ |
| `fields` | list[str] | `view` に従う | 返す項目に加える項目（`body`・種類ごとの項目・計算項目も可） |
| `exclude_fields` | list[str] | なし | 返す項目から除く項目 |
| `order_by` | list[{`field`, `direction`}] | `id` の昇順 | 複数キーの並べ替え。先のキーが優先。`direction` は `asc` / `desc`。日時が空の文書は末尾 |
| `group_by` | str | なし | 指定した項目の値ごとの件数を返す。配列の項目は要素ごとに数える |
| `limit` | int | 20 | 返す件数。最大 100 で、超えたら 100 に丸めて `notes` で知らせる |
| `cursor` | str | なし | 前回の `next_cursor`。ほかの引数は前回と同じにする |
| `skip` | int | 0 | 先頭から飛ばす件数 |
| `max_chars` | int | 20,000 | 結果全体の文字数の上限。上限は 40,000 |
| `max_chars_per_field` | int | 2,000（`view: full` は 10,000） | 長い値を末尾で切り、残りの文字数を添える |
| `snippets` | {`context_lines`, `max_per_doc`} | なし | 一致した行の前後だけを返す |
| `repeat_seen` | bool | `false` | この会話で返し済みの本文も返す |

<!-- /table -->

### 条件

```text
Group     = {"and": [Group | Condition, ...]} | {"or": [Group | Condition, ...]}
Condition = {"field": str, "op": enum, "values": [str, ...], "match": "any" | "all", "case_sensitive": bool}
```

<!-- table: data -->

| 項目 | 説明 |
| --- | --- |
| 入れ子 | 深さの制限は無い |
| `field` | メタデータのキー（`id`・`kind`・`name`・`tags`・`updated` など）、種類ごとの項目、`body`（本文）、`*`（全項目）、計算項目（`@chars` 文字数・`@path` ファイルのパス・`@sections` セクションの一覧） |
| `op` | `eq`・`ne`・`prefix`・`suffix`・`contains`・`not_contains`・`regex`・`gt`・`gte`・`lt`・`lte`・`exists`・`not_exists` |
| `values` | 文字列の配列。数値・日付は項目の型で解釈し、日付は `today`・`-7d` も受ける。`exists`・`not_exists` だけ省ける |
| `match` | `values` の複数を OR（`any`、既定）か AND（`all`）で比べる |
| `case_sensitive` | 既定 `false`。大文字小文字と全角半角（NFKC）を区別しない |

<!-- /table -->

### レスポンス

| フィールド | 説明 |
| --- | --- |
| `total_count` | 条件に当たった総件数。複数の配信元では配信元ごとにも返す |
| `returned` | 返した件数 |
| `next_cursor` | 続きがあるときだけ |
| `truncated` | `max_chars` で打ち切ったか |
| `notes` | 丸めた・打ち切った・読めなかったファイルの知らせと次の手 |
| `groups` | `group_by` のときの値ごとの件数 |
| `items[]` | 文書。ID で絞ったときは指定した順。各文書に `id`・`version`、`view: full` で `body`。複数の配信元を指したときは `source` が付く |
| `items[].path`・`items[].scope` | 文書の場所と返した範囲。[文書の場所と範囲](#文書の場所と範囲)のとおり。`view: ids`・`count` では持たない |

YAML として読めないファイルがあっても、そのファイルを除いて返し、`notes` で知らせます。

## write_docs

文書の作成・部分更新・置き換えを配列で受け、変更を当てた後の文書を配信元のスキーマと `validators[]` に通してから書き込みます。
書き込みの先は [配信元と権限](../はじめに/コアコンセプト/配信元と権限.md) の「書き込みの先」のとおりです。

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `operations` | list[Operation] | 必須 | 並べた順に当てる操作。1 回に 50 件まで |
| `atomic` | bool | `true` | `true` は 1 件でも失敗したら何も書かない。`false` は成功分を書き、失敗分を添字付きで返す |
| `dry_run` | bool | `false` | 本番と同じ検証・バージョンの確認・差分を返し、書き込まない |

<!-- table: data -->

| Operation のキー | 使える `op` | 説明 |
| --- | --- | --- |
| `op` | すべて | `create`（新しい文書）・`update`（部分更新）・`replace`（全項目の置き換え）。upsert は無い |
| `kind` | `create`（必須） | 種類（`documents[].id`）。スキーマと置き場所を決める |
| `id` | `update`・`replace`（必須）、`create`（省略可） | 対象の文書の ID。`create` で省くと `ids.format` から作る |
| `expected_version` | `update`・`replace`（必須） | 読んだときのバージョン。`update` では項目のパスごとのハッシュも受ける |
| `data` | `create`・`replace`（必須） | 文書の全項目 |
| `set` | `update` | 項目に値を入れる。オブジェクトは再帰的にマージし、配列と値は置き換える |
| `unset` | `update` | 消す項目のパスの配列 |
| `add_to` | `update` | 配列の項目の末尾へ要素を追加する |
| `remove_from` | `update` | 配列の項目から一致する要素を削除する |
| `text_edits` | `update` | `[{field, old, new, replace_all}]`。`replace_all` が `false` のとき `old` が 1 か所だけ一致すること |

<!-- /table -->

全ての操作を当ててから 1 回だけ検証し、通ったときだけ一時ファイルに書いてから置き換えます。
読み込み・検査・書き込みは配信元ごとの排他ロックの中で行い、書いた後に `generators[]` を流します。

レスポンスは `applied`（1 件以上を書いたか。`dry_run` は常に `false`）と `results[]` です。
`results[]` は `index`・`id`・`status`（`created`・`updated`・`replaced`・`failed`）・`version`・`diff`（`updated`・`replaced` と `dry_run`）・`errors`（`failed` のとき、項目のパス・決まり・直し方）を持ちます。

## delete_docs

文書を配列で受けて物理削除します。
Git の配信元で消した文書は Git で戻せます。

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `targets` | list[{`id`, `expected_version`}] | 必須 | 消す文書と読んだときのバージョン。1 回に 50 件まで |
| `on_referenced` | `fail` / `unlink` | `fail` | 他の文書の `related` から参照されているとき。`unlink` は参照も外して消す |
| `atomic`・`dry_run` | bool | `true`・`false` | `write_docs` と同じ |

レスポンスは `applied` と `results[]`（`status` は `deleted`・`failed`）、`on_referenced: unlink` のときの `unlinked[]`（参照を外した文書の `id`・`version`）です。
Git 管理外の配信元では、種類の `documents[].writable` が削除を許していることが要ります。

## describe

引数の数で返すものが変わります。

| 引数 | 返すもの |
| --- | --- |
| なし | 今の作業場所から使える配信元の一覧（`id`・権限 `read` / `write`・作業中か・`description`）と、作業場所 |
| `source` | その配信元の説明書（`instructions`）と種類（`kinds[]`）の一覧 |
| `source`・`kind` | その種類のスキーマ（YAML のまま） |

説明書には配信元に固有のことだけが記載されます。
タグの一覧・文書の件数は `search_docs` の `group_by`・`view: count` で取ります。

## list_changes

区間か、この会話で前回読んだ時点から今までに変わった文書・変わったキー・差分の行を返します。

<!-- table: data -->

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `from` | str | この会話で前回読んだ時点 | 区間の始点（commit・日時・ブランチ・タグ）。日時はその時点の最後の commit に解決する。Git 管理外の配信元では渡せない |
| `to` | str | 今の作業ツリー | 区間の終点。`from` を渡したときだけ |
| `filter` | Group か Condition | 全件 | `search_docs` と同じ条件で、対象の文書を絞る |
| `view` | `summary` / `full` | `summary` | `summary` は変わった文書と変わったキー、`full` は差分の行まで |
| `limit` | int | 20 | 返す文書の数。最大 100 |
| `cursor` | str | なし | 前回の `next_cursor` |
| `max_chars` | int | 20,000 | 結果全体の文字数の上限。上限は 40,000 |

<!-- /table -->

レスポンスは、解決した始点・終点（`range.from`・`range.to` の入力値・commit・日時）、`total_count`、`items[]`（`id`・`change` の `added` / `modified` / `deleted`・`keys`・`view: full` の `diff`・今の作業ツリーが終点のときの `path`・`scope`）、`truncated`、`notes` です。
前回読んだ時点は、`search_docs` が `state_dir` に記録した、文書ごとの最後に返した内容と比べます。

## trace_related

起点の文書かコードのパスから `related` をたどって、関連する文書を返します。

| 引数 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `from_ids` | list[str] | なし | 起点の文書の ID。`code_paths` とどちらか 1 つを渡す |
| `code_paths` | list[str] | なし | 起点のコードのパス（配信元の直下から）。`records`・`body_file` の行で、そのパスを本文に持つ文書を起点にする |
| `depth` | int | 2 | たどる深さ。1〜4 で、超えたら 4 に丸めて `notes` で知らせる |
| `direction` | `out` / `in` / `both` | `both` | `out` は起点の `related` が指す先、`in` は起点を `related` で指す文書 |
| `suggest` | bool | `false` | `true` で、関連の候補（同じ commit での変更・同じ会話での編集と閲覧）を上位 3 件返す |
| `repeat_seen` | bool | `false` | この会話で返し済みの相手の名前・概要文も返す |

一度たどった文書はたどりません。
`json` の各項目は、たどった文書の `path` と `scope: summary` を持ちます。
候補は `related` に書き込まないので、採用するときは `write_docs` で `related` に追加します。
たどった先が読めない配信元の文書は、ID だけを返します。

## エラー

エラーは `isError: true` のツール結果で返し、本文に原因と次の手を記載します。

<!-- table: data -->

| エラー | 発生条件 | 本文に記載すること |
| --- | --- | --- |
| SourceNotReadableError | `cwd` が配信元の `scope.read`・`scope.write` に当たらない、または `cwd` が無い | 今の作業場所から使える配信元の一覧 |
| SourceNotWritableError | `cwd` が配信元の `scope.write` に当たらない | 今の作業場所から使える配信元の一覧 |
| SourceNotServedError | 起動時の検証で外したか `enabled: false` の配信元を指した | 違反したキーのパスと理由 |
| WorktreeNotMatchedError | `worktree` が配信元の `worktrees` に当たらない | 渡したパスと `worktrees` の値 |
| TargetIsCloneError | Git の配信元で、書く先がクローン本体になる | `worktree` でワークツリーを指すこと |
| InvalidArgumentError | `filter`・`order_by`・`group_by`・Operation の中の知らない項目・型の合わない値、50 件を超える操作、必須のキーの欠け、`text_edits` の `old` が 1 か所に一致しない、`ref` を渡せない配信元に `ref`・`from`・`to` を渡した | 項目のパス・期待する型・実際の値と、`describe(source, kind)` でスキーマを見ること |
| RefNotFoundError | `ref`・`from`・`to` を commit に解決できない | 解決できなかった値 |
| UnknownKindError | `kind` が配信元の種類に無い | その配信元の種類の一覧 |
| DocumentNotFoundError | 指した ID の文書が無い | 見つからなかった ID と、近い ID の候補 |
| VersionMismatchError | `expected_version` が今のバージョンと違う | 今のバージョンと差分、読み直して呼び直すこと |
| ValidationFailedError | 変更を当てた後の文書がスキーマか `validators[]` に通らない（`atomic: true`） | 違反ごとの添字・パス・決まり・直し方 |
| DocumentReferencedError | `on_referenced: fail` で、消す文書が他の文書の `related` から参照されている | 参照元の ID と `on_referenced: unlink` |
| DeleteNotAllowedError | Git 管理外の配信元で、種類の `documents[].writable` が削除を許していない | 種類の ID と `documents[].writable` のパス |
| LastReadNotFoundError | `list_changes` の `from` を省いたが、この会話で本文を読んだ記録が無い | `from` を渡すこと |

<!-- /table -->

`search_docs` の返す量が上限に達したときはエラーにせず、`truncated` と `next_cursor` を返します。
`notes` に、`fields` を絞るか `view: ids` で取り直す手を添えます。
