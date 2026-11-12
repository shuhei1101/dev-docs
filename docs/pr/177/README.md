# プロンプトファイルの kind に agent を追加し、templates/prompt.schema.yaml と prompt_doc の型へ反映する

## 概要

プロンプトファイルの `kind` に `agent`（Claude Code のエージェントに `--append-system-prompt` で指定するシステムプロンプト）を追加し、dev-docs が `kind: agent` のプロンプトを検査・描画できるようにする。

## 背景

[Issue #156](https://github.com/shuhei1101/dev-docs/issues/156) の要望。
knowledge の [shuhei1101/knowledge#240](https://github.com/shuhei1101/knowledge/pull/240)（マージ済み）で、原本の `schemas/prompt.schema.yaml` の `kind` に `agent` が追加された。
dev-docs が持つコピー `templates/prompt.schema.yaml` と、プロンプトを読む `prompt_doc` の型は `llm`・`hook`・`instructions`・`tool` の 4 つのままのため、`kind: agent` のプロンプトを検査で違反にする。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
