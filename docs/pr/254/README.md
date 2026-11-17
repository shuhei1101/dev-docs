# 文書の画面の結合テスト body_without_preflight の閉じた凡例の前提を、mdmark の develop の最新に合わせる

## 概要

文書の画面の結合テスト `body_without_preflight` が、mdmark の develop の最新でも、本文に画面の基本のスタイル（Tailwind の Preflight）を適用しないことを確認できるようにする。

## 背景

[#245](https://github.com/shuhei1101/dev-docs/issues/245) の要望。
[#240](https://github.com/shuhei1101/dev-docs/issues/240) で文書の画面は mdmark の既定の参照を develop の最新（jsDelivr の `@develop`）にした。
作業 PR [#212](https://github.com/shuhei1101/dev-docs/pull/212) の結合テストを mdmark の develop の最新の dist（shuhei1101/mdmark の [3730097](https://github.com/shuhei1101/mdmark/commit/373009769ef1444847b12c29f003f884125ef6ac)）で実行すると、`body_without_preflight` が `expect(styles.hiddenLegend).toBe("flex")`（Received: `undefined`）で fail した。
テストは本文の map のシーケンス図に閉じた凡例 `.mdmark-diagram-legend[hidden]` があることを前提にしているが、develop の最新の mdmark はその要素を出さない。
jsDelivr の `@develop` のキャッシュが更新されると、develop の結合テストでも同じ fail が出る。

閉じた凡例の確認は、[#232](https://github.com/shuhei1101/dev-docs/pull/232) で Preflight の `[hidden]` の `display: none !important` を本文に適用しないようにしたことを確認するために配置した。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.md) | 文書の画面の結合テストの計画書 |
