# AI Monitor v0.3.0 の配布物へ追従する

## 概要

dev-docs が、AI Monitor v0.3.0 の配布物（サイトの共通の部品・規約）に追従した状態になる。

## 背景

[Issue #35](https://github.com/shuhei1101/dev-docs/issues/35) の要望。
AI Monitor が v0.3.0 のタグを打ち、配布物リストの分類ごとに配布先の行動が届いた。
[扱いの判断](https://github.com/shuhei1101/dev-docs/issues/35#issuecomment-6502067358) で、テンプレート（`*.schema.yaml`）とルール索引は dev-docs が既に v0.3.0 の内容で持っており、設計書の変換と `rules.yaml` への行の追加は対象なしと決まっている。
develop の `ai-monitor-version.ini` は `v0.2.0` のまま、`docs/_theme/` は `_data/nav.project.yml` だけで、控え `ai-monitor-theme.yaml` は無い。
依存の [#32](https://github.com/shuhei1101/dev-docs/issues/32)（PR [#33](https://github.com/shuhei1101/dev-docs/pull/33)）はマージ済み。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（設計書はそろっている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（取り込みは配布元の CLI で行い、未検証の技術機構に依存しない）
- [x] ~~複合ユースケース設計~~（影響なし: 配布物の取り込みと文書の書式の修正で、利用者の流れを変えない）
- [x] ~~デザインスタイル選定~~（dev-docs の画面を追加・変更しない）
- [x] ~~画面一覧・画面遷移~~（画面の追加・削除と画面遷移の変更を含まない）
- [x] ~~単一ユースケース設計~~（影響なし）
- [x] ~~モック作成~~（dev-docs の画面を追加・変更しない）
- [x] ~~インターフェース定義設計~~（影響なし）
- [x] ~~部品設計~~（影響なし）
- [x] ~~画面設計~~（dev-docs の画面を変えない）
- [x] ~~モジュール構成設計~~（影響なし）
- [ ] ドキュメント修正（docs/_theme/・ai-monitor-theme.yaml・ai-monitor-version.ini・dev/設計書/デザイン方針.md・docs/リファレンス/CLI.md・docs/リファレンス/文書のMCP.md・docs/リファレンス/管理のMCP.md・docs/リファレンス/設定.md・docs/使い方/dev-docsを更新する.md・docs/使い方/配信元を配信する.md）
- [x] ~~単体テスト作成~~（コードを変えない）
- [x] ~~実装~~（コードを変えない）
- [x] ~~結合テスト作成~~（コードを変えない）
- [x] ~~E2E テスト作成~~（シナリオに影響しない）
