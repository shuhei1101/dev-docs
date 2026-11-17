# 変換の項目の見出しと参照のアンカーで、同じ見出しの 2 つ目以降のアンカーと見出しを出さない子のパスを修正する

## 概要

文書の参照（`id:{ID}#{項目のパス}`）のリンクが、同じ見出しの 2 つ目以降を指したときにその見出しへ飛び、画面の変換が見出しを出さない子を指したときに無い見出しのアンカーを付けないようにする。

## 背景

[Issue #297](https://github.com/shuhei1101/dev-docs/issues/297) の要望で、[#294](https://github.com/shuhei1101/dev-docs/issues/294) と [#295](https://github.com/shuhei1101/dev-docs/issues/295) をまとめて対応する。
どちらも [#292](https://github.com/shuhei1101/dev-docs/pull/292)（起点 Issue [#288](https://github.com/shuhei1101/dev-docs/issues/288)）のスコープ外から切り出した。
develop の `src/dev_docs/features/convert/inline.py` の `heading_anchor` は見出しの文字列だけからアンカーを作るため、`functions[main#3]` のリンクは 1 つ目の `main` の見出しへ飛ぶ。
`src/dev_docs/features/convert/markdown.py` の `item_heading` は、値が空の子と `x-hidden` の子を指すパスにも見出しを返却する。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
