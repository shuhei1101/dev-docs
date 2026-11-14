# 開発用のスクリプト・設定のコード（scripts/・eslint.config.js・frontend/.storybook/・frontend/scripts/）のコメントと docstring の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

`scripts/build_pages.py`・`eslint.config.js`・`frontend/.storybook/preview.tsx`・`frontend/scripts/export_openapi.py` のコメントと docstring の文言を、AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #208](https://github.com/shuhei1101/dev-docs/issues/208) の要望。
[PR #206](https://github.com/shuhei1101/dev-docs/pull/206)（[#189](https://github.com/shuhei1101/dev-docs/issues/189)。`tests/` と `plugins/dev-docs/` のコメントと docstring）の現状調査で見つかり、#189 のスコープ外として切り出された。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、どのサブシステムにも属さない `scripts/build_pages.py` の変更方針 |
| [画面](./画面.md) | 画面の開発用の設定とスクリプトの計画書 |
