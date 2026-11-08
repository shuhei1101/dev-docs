# write_docs の検査で、Markdown のキーの値を mdmark の点検に通し、警告があれば書き込まない

## 概要

エージェントが `write_docs` で書き込む文書の Markdown の値に mdmark の記法・図の部品の誤りがあれば、書き込まずに警告を受け取れるようにする。

## 背景

[#89](https://github.com/shuhei1101/dev-docs/issues/89) の要望。
`write_docs` の検査はスキーマと `validators[]` だけに通すため、Markdown の値に図の定義の誤りがあっても書き込める。
誤りは画面で描いたときに「書き方の警告」として初めて分かる。
依存先の [shuhei1101/mdmark#288](https://github.com/shuhei1101/mdmark/issues/288) は [shuhei1101/mdmark#328](https://github.com/shuhei1101/mdmark/pull/328) で develop へ入り、`mdmark check` の `--text`・`--file --key` と MCP の `check` が、描画時の「書き方の警告」と同じ内容を返す。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響範囲 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [反映作業](./反映作業/index.yaml) | マージの後のサーバーの再起動 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（mdmark の点検は mdmark#328 で検証済みで、外部プロセスの呼び出しは既存の `integrations/scripts.py` と同じ方式のため）
- [x] ~~複合ユースケース設計~~（影響なし: ユースケースの流れを変えない）
- [x] ~~デザインスタイル選定~~（画面を変えない）
- [x] ~~画面一覧・画面遷移~~（画面を変えない）
- [x] 単一ユースケース設計
- [x] ~~モック作成~~（画面を変えない）
- [x] インターフェース定義設計
- [x] ~~部品設計~~（画面の部品を変えない）
- [x] ~~画面設計~~（画面を変えない）
- [x] モジュール構成設計
- [x] ドキュメント修正（content/prompts/mcp/docs/tools/write-docs.yaml・dev/設計書/外部ライブラリ/mdmark.yaml・plugins/dev-docs/skills/global-setup/SKILL.md・docs/使い方/dev-docsを入れる.md・docs/リファレンス/文書のMCP.md）
- [x] 単体テスト作成
- [x] 実装
- [x] 結合テスト作成
- [x] E2E テスト作成
