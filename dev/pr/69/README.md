# SessionStart の注入文・MCP の instructions・ツールの description をプロンプトの YAML に移し、converters[] に変換の結果をキャッシュしない指定を設ける

## 概要

エージェントは、`content/prompts/` の YAML から読んだ文書の MCP の instructions とツールの description で、MCP を使う場面と grep・Read が向く場面を読めるようになる。
配信元は `converters[]` の行に `cache: false` を書き、本文の外のファイルを読む変換を、文書を開くたびに動かせるようになる。

## 背景

[Issue #68](https://github.com/shuhei1101/dev-docs/issues/68) は [#48](https://github.com/shuhei1101/dev-docs/issues/48)・[#64](https://github.com/shuhei1101/dev-docs/issues/64) の束。

#48: AI Monitor のエージェントの dev-docs の MCP の呼び出しが 24 時間で 0 回だった（2026-10-30〜31 の Loki の集計）。
今の注入文は MCP の使い方の 5 行で、使う場面と grep・Read が向く場面が無く、ツールの description も場面まで書くのは `trace_related` だけ。
文はコードの文字列で持っている（`session_context/types.py`・`server/mcp/docs.py`）。
プロンプトの YAML の形とスキーマは shuhei1101/knowledge#128、書き分けの規約は shuhei1101/knowledge#129 で決まり、画面での配信は [#56](https://github.com/shuhei1101/dev-docs/pull/56) で入った。

#64: 変換の結果の控えのキーは本文のハッシュを含み、本文の外のファイルは含まない。
AI Monitor のフェーズの変換は `ref` で参照先のフェーズを読むので、参照先を書き換えても古い Markdown が返り続ける（起点 shuhei1101/ai-monitor#3107）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | サーバーの計画書（プロンプトの YAML の読み込みと描画・`converters[].cache`） |
| [管理用プラグイン](./管理用プラグイン.md) | プラグインの計画書（SessionStart のフックの設計書） |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（設計書は揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない。プロンプトの YAML の Jinja2 の描画は #56 で動いている）
- [x] 複合ユースケース設計
- [x] ~~デザインスタイル選定~~（利用者に見える画面の見た目が変わらない）
- [x] ~~画面一覧・画面遷移~~（利用者に見える画面の見た目が変わらない）
- [x] 単一ユースケース設計
- [x] ~~モック作成~~（利用者に見える画面の見た目が変わらない）
- [x] インターフェース定義設計
- [x] ~~部品設計~~（画面の部品を変えない）
- [x] ~~画面設計~~（変更が画面に及ばない）
- [x] モジュール構成設計
- [ ] ドキュメント修正（docs/リファレンス/文書のMCP.md・docs/はじめに/コアコンセプト/管理用プラグイン.md・docs/はじめに/コアコンセプト/文書のメタデータ.md・docs/リファレンス/設定.md・docs/リファレンス/CLI.md・docs/使い方/配信元を配信する.md）
- [ ] 単体テスト作成
- [ ] 実装
- [ ] 結合テスト作成
- [ ] E2E テスト作成
