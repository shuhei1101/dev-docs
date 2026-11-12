# dev-docs 自身の文書を project-index.yaml で配信し、タグで引けるようにする

## 概要

dev-docs 自身の `docs/` の文書を、リポジトリの直下の `project-index.yaml` で project-index の配信元にし、AI がタグ・名前・概要文で検索できるようにする。

## 背景

[Issue #24](https://github.com/shuhei1101/dev-docs/issues/24) の要望。
直下に配信元の設定が無く、dev-docs 自身の文書は配信されていない。
[PR #22](https://github.com/shuhei1101/dev-docs/pull/22) で `docs/guide/` に配置した 2 つの判定フローチャートは、配信されない front matter に `tags` を持つだけで、検索で見つからない。
配信元の設定のスキーマは [#32](https://github.com/shuhei1101/dev-docs/issues/32)・[shuhei1101/alias-inject#37](https://github.com/shuhei1101/alias-inject/issues/37) で決まり、既定のファイル名は [#163](https://github.com/shuhei1101/dev-docs/pull/163) で `project-index.yaml` になった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [反映作業](./反映作業/index.yaml) | 端末の設定への配信元の追加 |
