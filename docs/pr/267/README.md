# nav の auto.group_by で共通のメタデータを指定してグループに分けられるようにする

## 概要

配信元の設定を書く利用者が、nav の `auto.group_by` に共通のメタデータ（`main_tags`・`tags`、行の `metadata` で対応付けた `category` など）を指定して、サイドバーの文書をその値ごとのグループに分けられるようにする。

## 背景

[Issue #251](https://github.com/shuhei1101/dev-docs/issues/251) の要望。`auto.group_by` は文書の YAML の値を項目のパスで引くため、共通のメタデータを指定すると全ての文書が「その他」のグループに入る。[shuhei1101/project-index#111](https://github.com/shuhei1101/project-index/pull/111) では、モジュール構成を `group_by: main_tags` で分けられず、分類ごとの `group` と名前の前方一致の `filter` で回避している。`auto.filter` の共通のキーは [#249](https://github.com/shuhei1101/dev-docs/issues/249)（[#262](https://github.com/shuhei1101/dev-docs/pull/262)）で、行の `metadata` で対応付けた列から値を引くように直った。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
