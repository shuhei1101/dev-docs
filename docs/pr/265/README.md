# 配信元の行の storage の持ち回しと、起動直後の読み込み中の配信元の扱いを追加する

## 概要

利用者が設定画面で配信元の読み書きの方法（`storage`）を表示・修正でき、保存しても消えないようにする。
project-index の起動の直後でも、起動の通知と管理の MCP の `status` が全ての配信元の読み込みを待たずに応答し、読み込み中の配信元を読み込み中として扱えるようにする。

## 背景

[#264](https://github.com/shuhei1101/dev-docs/issues/264) は、同じ種類（`kind:機能の拡張`）で対象が重なる次の Issue の束。

- [#235](https://github.com/shuhei1101/dev-docs/issues/235): [shuhei1101/project-index#87](https://github.com/shuhei1101/project-index/issues/87) で端末の設定の `sources[]` の行に `storage`（`disk` / `git`）が増えた。dev-docs は設定画面・端末の設定の取得と保存・`dev-docs migrate` で行を既知のキーだけで組み立て直すため、保存すると `storage` が消え、`disk` の配信元が `git` に戻る
- [#250](https://github.com/shuhei1101/dev-docs/issues/250): project-index の `GET /sources` は、起動の直後に全ての配信元の読み込みが終わるまで応答しない（[shuhei1101/project-index#97](https://github.com/shuhei1101/project-index/issues/97)）。[shuhei1101/project-index#103](https://github.com/shuhei1101/project-index/pull/103) で `include_loading=true` と状態 `loading` が増えたが、dev-docs の `list_sources` は付けずに呼んでいる

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 端末の設定の取得・保存・移し替えの `storage` と、`list_sources`・起動の通知・`status` の `loading` の計画書 |
| [画面](./画面.md) | 設定画面の `sources[]` の組み立てと、配信元のダイアログの `storage` の計画書 |
