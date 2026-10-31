# records の行のスキーマの当て方をそろえ、管理用の YAML の行の文書の相対リンクと SessionStart の打ち切りを修正する

## 概要

エージェントは、管理用の YAML（`files.yaml`）の文書を検索しても毎回同じスキーマの警告を受け取らず、利用者は管理用の YAML の行の文書の本文の相対リンクから文書を開ける。
SessionStart のフックは session-context の応答を待ちきり、配信元の一覧をセッションの文脈に入れる。

## 背景

[Issue #53](https://github.com/shuhei1101/dev-docs/issues/53) の要望で、計画の行 [#39](https://github.com/shuhei1101/dev-docs/issues/39)・[#45](https://github.com/shuhei1101/dev-docs/issues/45)・[#46](https://github.com/shuhei1101/dev-docs/issues/46) の束。

- #39: `records: files` の行で、`DocumentChecker.check` が `records` の要素 1 つずつに、ファイル全体のスキーマ（`templates/files.schema.yaml` のコピー。最上位で `files` を必須にする）を当てる。`/dev-docs:setup` が作る組み合わせのまま、files の文書の検索結果に毎回 `'files' is a required property` が付き、`check_project` は検出しない
- #45: [PR #36](https://github.com/shuhei1101/dev-docs/pull/36) で作った画面の `doc-body.tsx` が、本文の相対リンクを画面のパス（YAML のパスとファイルのパスの連結）を基準に解決し、管理用の YAML の行の文書で「文書が見つかりません」になる（[r4425603859](https://github.com/shuhei1101/dev-docs/pull/36#discussion_r4425603859)）
- #46: `session_start.py` の `CONTEXT_TIMEOUT_SEC = 3` で session-context を打ち切ると、配信元の一覧の代わりに「dev-docs の文脈を取れませんでした」が文脈に入る。2026-10-31 の手元の計測で 1 回目の応答が 2 分近く返らず、同じ時刻の `/mcp/` も打ち切られていた

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | サーバーの計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | プラグインの計画書 |
| [画面](./画面.md) | 画面の計画書 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（対象の設計書は develop にそろっている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない）
- [x] ~~複合ユースケース設計~~（影響なし: 単一ユースケースの箱のつながりは変わらない）
- [x] ~~デザインスタイル選定~~（画面の見た目が変わらない）
- [x] ~~画面一覧・画面遷移~~（画面の見た目が変わらない）
- [x] 単一ユースケース設計
- [x] ~~モック作成~~（画面の見た目が変わらない）
- [x] インターフェース定義設計
- [x] ~~部品設計~~（部品の引数・状態が変わらない）
- [x] ~~画面設計~~（UI 項目と操作が変わらない。変わるのは本文のリンクの行き先の解決だけ）
- [x] モジュール構成設計
- [x] ドキュメント修正（templates/files.schema.yaml・docs/リファレンス/設定.md・docs/リファレンス/管理のMCP.md）
- [x] 単体テスト作成
- [ ] 実装
- [ ] 結合テスト作成
- [ ] E2E テスト作成
