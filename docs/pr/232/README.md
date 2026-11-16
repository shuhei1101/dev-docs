# 文書の画面の本文の見た目を、単独の mdmark で書き出した HTML と揃える

## 概要

利用者が dev-docs の文書の画面で、単独の mdmark（`mdmark export` で書き出した HTML）と同じ見た目の本文を読めるようにする。

## 背景

[#227](https://github.com/shuhei1101/dev-docs/issues/227) の要望。dev-docs の文書の画面は mdmark で本文を描いているのに、単独で使用する mdmark の見た目と違い、きれいでないと利用者が報告した（TH-1142）。
話し合いの確認（調査 R-18）では、表・図・見出しが mdmark の部品で描かれていることまでは確かめたが、どこが違うかは特定できていない。

画面は Tailwind の基本のスタイル（`@layer base`）と色のトークンを `frontend/src/index.css` に持ち、mdmark の `dist/index.css` は jsDelivr から `use-mdmark.ts` が `<link>` で読み込む。
本文は `doc-main.tsx` の本文の領域の枠（`min-w-0 flex-1 space-y-4 py-6`）の中で `doc-body.tsx` が描く。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響範囲 |
| [画面](./画面.md) | 文書の画面の本文のスタイルの計画書 |
