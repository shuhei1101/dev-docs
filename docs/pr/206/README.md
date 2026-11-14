# テストコード（tests/）と管理用プラグイン（plugins/dev-docs/）のコメントと docstring の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

`tests/` と `plugins/dev-docs/` のコメントと docstring の文言を、AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #189](https://github.com/shuhei1101/dev-docs/issues/189) の要望。
[PR #188](https://github.com/shuhei1101/dev-docs/pull/188)（[#150](https://github.com/shuhei1101/dev-docs/issues/150)。`src/dev_docs/` のコメントと docstring）の現状調査で見つかり、#150 のスコープ外として切り出された。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーを検証するテストの計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインのフックとテストの計画書 |
| [画面](./画面.md) | 画面を検証するテストの計画書 |
