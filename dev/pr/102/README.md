# ER 図を mdmark の部品で描画し、往復編集で引用符を維持し、本文の id: のリンクを解決する

## 概要

利用者が、ER 図を列つきの mdmark の ER 図の部品で読み、本文の `id:` のリンクから同じ配信元の文書へ移動できるようになる。
エージェントが `write_docs`・`delete_docs` で文書を書き換えても、変更していない項目の引用符が維持される。

## 背景

[Issue #100](https://github.com/shuhei1101/dev-docs/issues/100) は次の 3 件の束。

- [#59](https://github.com/shuhei1101/dev-docs/issues/59): 汎用の描画（`features/convert/diagrams.py`）は `x-diagram` の ER を Mermaid の `erDiagram` で出すが、画面も mdmark も Mermaid を描画しない。ER 図の実体の列も空になる。ER 以外の図は [#90](https://github.com/shuhei1101/dev-docs/pull/90)（[#55](https://github.com/shuhei1101/dev-docs/issues/55)）で mdmark の部品にした
- [#91](https://github.com/shuhei1101/dev-docs/issues/91): `write_docs` の `update` で、変更していない項目の引用符まで書き換わる。[knowledge#155](https://github.com/shuhei1101/knowledge/pull/155) の作業で見つかった
- [#97](https://github.com/shuhei1101/dev-docs/issues/97): 共通のスキーマ（`templates/common.schema.yaml` の `body`）は本文のリンクを `[名前](id:{文書の ID})` で記載すると定めているが、変換は型 `ref` の値だけをリンクにしている。使う側は [ai-monitor#3198](https://github.com/shuhei1101/ai-monitor/pull/3198)。mermaid の `click` は [#98](https://github.com/shuhei1101/dev-docs/issues/98) へ分けた

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない。ER 図は mdmark の ER 図の部品（[mdmark#298](https://github.com/shuhei1101/mdmark/pull/298)）、引用符は ruamel.yaml の `preserve_quotes` で扱う）
- [x] ~~複合ユースケース設計~~（影響なし: 既存フローの範囲内）
- [x] ~~デザインスタイル選定~~（デザイン方針があり、見た目の方向を変えない）
- [x] ~~画面一覧・画面遷移~~（画面の追加・削除と画面遷移の変更を含まない）
- [x] 単一ユースケース設計
- [x] ~~モック作成~~（ER 図の見た目は mdmark の部品が決め、本文のリンクは既存のリンクと同じ表示で、作り手が見た目を決める余地が無い）
- [x] インターフェース定義設計
- [x] ~~部品設計~~（画面の部品は変わらない）
- [x] ~~画面設計~~（変わるのは Markdown の本文だけで、UI 項目と操作は変わらない）
- [x] モジュール構成設計
- [x] ドキュメント修正（docs/リファレンス/設定.md・設計書/外部ライブラリ/mdmark.yaml・設計書/外部ライブラリ/ruamel.yaml.yaml）
- [x] 単体テスト作成
- [x] 実装
- [x] 結合テスト作成
- [x] E2E テスト作成
