# 画面が広いとき、文書の画面の本文と表をその幅まで広げる

## 概要

画面が広いとき、利用者が文書の画面の本文と表をその幅で参照できるようにする。

## 背景

[Issue #303](https://github.com/shuhei1101/dev-docs/issues/303) の要望。
ブラウザの拡大率を下げて画面を広くしても、本文の幅が 1,240px から広がらず、左右の余白が増えるだけになる。
develop の [frontend/src/features/docs/doc-view/doc-view-screen.tsx](https://github.com/shuhei1101/dev-docs/blob/7ef1589/frontend/src/features/docs/doc-view/doc-view-screen.tsx#L136) は、サイドバーと本文を並べるコンテナの幅の上限を `max-w-screen-2xl`（1,536px）にしている。
1,536px から左右の余白（`px-4`）・サイドバー（`w-60`）・間隔（`gap-6`）を引いた 1,240px が本文の幅になる。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.mark.md) | 画面の計画書 |
