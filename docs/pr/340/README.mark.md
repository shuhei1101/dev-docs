# 文書の画面の検索のモーダル・差分のバーのラベルの色・画面全体のスクロールバー・サイドバーの折り返しを修正する

## 概要

利用者が、文書の画面の検索で結果を全件スクロールして配信元を横断して探せ、差分の案内のラベルがコントラストの基準を満たし、画面全体のスクロールバーが出ず、サイドバーの名前が 1 行で並ぶようにする。

## 背景

[Issue #339](https://github.com/shuhei1101/dev-docs/issues/339) の束（[#338](https://github.com/shuhei1101/dev-docs/issues/338)・[#334](https://github.com/shuhei1101/dev-docs/issues/334)・[#337](https://github.com/shuhei1101/dev-docs/issues/337)・[#336](https://github.com/shuhei1101/dev-docs/issues/336)）の要望。
検索のダイアログは結果をスクロールできず上の 3 件しか見られず、開いている配信元の中しか検索できない。
差分の案内の「比較元」「比較先」のラベルは `bg-muted` の上の `text-muted-foreground` で、axe の `color-contrast` が出る。
文書の画面は骨格の高さ（`min-h-screen` と、`sticky` のサイドバーの `max-h-screen`）が表示領域を超え、開いた直後から画面全体に縦のスクロールバーが出る。
サイドバーは [#333](https://github.com/shuhei1101/dev-docs/pull/333) で幅を変えられるようになったが、長い名前が折り返して一覧の行を見分けにくい。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.mark.md) | 画面の計画書 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
