# 画面の検索の一致した行の数を、project-index の本物の応答につなぐ

## 概要

画面の検索の一致した行の数（`items[].matchCount`）を、`matchCount` を返却する本物の project-index の応答で確かめ、外部 API の設計書を本物と照合した内容にする。

## 背景

[#340](https://github.com/shuhei1101/dev-docs/pull/340) で、画面の検索（IF-155-16）の `items[].matchCount` を [shuhei1101/project-index#299](https://github.com/shuhei1101/project-index/issues/299) の入出力に沿ったモックで先に作った。
project-index 側は [shuhei1101/project-index#300](https://github.com/shuhei1101/project-index/pull/300)（develop の `2588d67`）で `matchCount` を返却するようになったため、[#341](https://github.com/shuhei1101/dev-docs/issues/341) の要望で本物の応答につなぐ。
計画の行の決定で、project-index のリリースのタグは待たず、develop へマージされた commit で着手する。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 画面の検索の結合テストと外部 API の設計書の計画書 |
| [画面](./画面.mark.md) | 検索のダイアログの並び順と「一致 N 行」の確認の計画書 |
