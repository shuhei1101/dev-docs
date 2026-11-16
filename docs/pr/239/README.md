# 設計書・モックに残る「作り直す」（CMD-155-1・IF-155-10・LIB-155-6・prompt-doc.js）を AI slop の単語の対応表に合わせて「再作成する」へ修正する

## 概要

設計書とモックに残る「作り直す」（`docs/dev-command/CMD-155-1.yaml`・`docs/interface/IF-155-10.yaml`・`docs/library/LIB-155-6.yaml`・`docs/mock/refs/56/assets/prompt-doc.js`）を、AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #221](https://github.com/shuhei1101/dev-docs/issues/221) の要望。
[PR #219](https://github.com/shuhei1101/dev-docs/pull/219)（[#216](https://github.com/shuhei1101/dev-docs/issues/216)。`docs/module/MOD-192-1.py.yaml` の文言）の現状調査で見つかり、#216 のスコープ外として切り出された。
[PR #214](https://github.com/shuhei1101/dev-docs/pull/214)（[#208](https://github.com/shuhei1101/dev-docs/issues/208)）と PR #219 は「作り直す」を「再作成する」に置き換えている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、どのサブシステムにも属さない設計書の変更方針 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | `docs/interface/IF-155-10.yaml` の変更方針 |
| [画面](./画面.md) | `docs/mock/refs/56/assets/prompt-doc.js` の変更方針 |
