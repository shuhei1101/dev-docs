# 管理用プラグインのセッション開始のフックが返却する文言を、AI slop の単語の対応表に合わせて修正する

## 概要

管理用プラグインのセッション開始のフックが Claude Code の文脈（`additionalContext`）へ返却する文言を、knowledge の AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #134](https://github.com/shuhei1101/dev-docs/issues/134) の要望。
[PR #133](https://github.com/shuhei1101/dev-docs/pull/133)（起点 [Issue #117](https://github.com/shuhei1101/dev-docs/issues/117)）は `src/dev_docs/` の MCP の応答の文言を修正し、`plugins/` のフックの文言を #134 に切り出した。
MCP の応答は `/mcp で再接続して`・`（この会話で返却済み）`・`再取得してください` になったが、フックは `つなぎ直して`・`返し済み`・`取り直せます` のまま残っている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインの計画書 |
