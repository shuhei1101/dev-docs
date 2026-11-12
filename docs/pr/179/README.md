# 画面の結合テストを、列の表示のメニューの照合と全件実行での時間切れについて修正する

## 概要

画面の結合テスト（`npm run test:integration`）を全件実行したとき、列の表示のメニューの 4 件と、検索のダイアログ・トップバーのストーリーの spec が pass するようにする。

## 背景

[Issue #178](https://github.com/shuhei1101/dev-docs/issues/178) は [#157](https://github.com/shuhei1101/dev-docs/issues/157)・[#170](https://github.com/shuhei1101/dev-docs/issues/170) の束。
#157 は、mdmark v0.10.0 で表のボタンの名前が `列の表示` から `テーブル設定` に変わり、`doc-view-screen.spec.ts` の「列の表示のメニュー」の 4 件が fail した事象。依存の [#99](https://github.com/shuhei1101/dev-docs/issues/99)（[PR #101](https://github.com/shuhei1101/dev-docs/pull/101)）のマージで、develop の照合は `テーブル設定` に置き換わっている。
#170 は、全件実行で `search-dialog.spec.ts`・`topbar.spec.ts` がストーリーの描画を待つ 15 秒の時間切れで fail し、単独で実行すると pass する事象。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.md) | 画面の計画書 |
