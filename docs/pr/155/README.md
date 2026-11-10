# dev-docs 自身の文書を dev/ から docs/ の種類ごとのフォルダへ移し、設計書を ID のファイル名にする

## 概要

dev-docs 自身の文書を `dev/` から、ai-monitor#3307 と同じ構成（`docs/` の下を種類だけのフォルダ・フラット・ID のファイル名、Schema は `schemas/`）へ 1 回の PR で移し、`dev/` を廃止する。

## 背景

[Issue #7](https://github.com/shuhei1101/dev-docs/issues/7) の要望。
[Issue #2](https://github.com/shuhei1101/dev-docs/issues/2) の構成方針は「文書は `docs/` だけに置く（`dev/` は作らない）」だが、立ち上げの [PR #6](https://github.com/shuhei1101/dev-docs/pull/6) は ai-monitor の工程に合わせて `dev/` に設計書・テンプレート・規約・PR ドキュメントを配置した。

ai-monitor は [shuhei1101/ai-monitor#3307](https://github.com/shuhei1101/ai-monitor/pull/3307)（[shuhei1101/ai-monitor#2973](https://github.com/shuhei1101/ai-monitor/issues/2973)）で手順・ツールを `docs/` 前提にする。
`dev/` が残る間は、ai-monitor の設計書の検証・Markdown の生成（`python -m ai_monitor.design_docs`）が dev-docs で動かない。
ID のファイル名にするため、設計書への `id` の振り付けと参照の ID 化を [#74](https://github.com/shuhei1101/dev-docs/issues/74) から移した（[判断](https://github.com/shuhei1101/dev-docs/issues/7#issuecomment-6739413202)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と置き場所の対応 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの設計書の移し方 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインの設計書の移し方 |
| [画面](./画面.md) | 画面の設計書の移し方 |
