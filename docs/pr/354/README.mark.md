# 画面の表・コメントを mdmark の部品のカスタム要素に置き換え、用語集の「編集中の変更」の説明に文書の本文を含める

## 概要

利用者が、メタデータの画面・設定画面・文書の画面の表とコメントを、文書の本文と同じ mdmark の部品の外観と操作で扱えるようにする。
あわせて、用語集の「編集中の変更」の説明を、文書の画面で編集した本文の変更も含む記述にする。

## 背景

[Issue #353](https://github.com/shuhei1101/dev-docs/issues/353) の束（[#348](https://github.com/shuhei1101/dev-docs/issues/348)・[#352](https://github.com/shuhei1101/dev-docs/issues/352)）の要望。
画面の表とコメントのパネルは、mdmark の部品のカスタム要素を使用せずに組んでいる。
mdmark の配布物に `<mdmark-table>`・`<mdmark-comments>` などのカスタム要素が入り（[shuhei1101/mdmark#793](https://github.com/shuhei1101/mdmark/issues/793)・[shuhei1101/mdmark#797](https://github.com/shuhei1101/mdmark/issues/797)）、knowledge の規約『共通コンポーネント規約』に、画面の表・ボード・グラフ・図・コメントをそれらで組む決まりが入った（[shuhei1101/knowledge#598](https://github.com/shuhei1101/knowledge/issues/598)）。
用語集の「編集中の変更」は、[#335](https://github.com/shuhei1101/dev-docs/pull/335) で追加した文書の画面の本文の変更を含めておらず、単一 UC シナリオ『利用者が画面で編集中の変更をまとめて直コミットする』と合っていない（[#351](https://github.com/shuhei1101/dev-docs/pull/351) から切り出した）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.mark.md) | 画面の計画書 |
