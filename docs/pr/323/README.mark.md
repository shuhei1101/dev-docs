# 画面で、本文の直コミットを断る種類の本文の編集を出さず、search_exclude に該当する文書を薄く表示する・隠す

## 概要

利用者が、メタデータの画面で本文の直コミットを断る種類の文書の本文を編集して断られることがなくなり、文書の画面で検索から除外される文書を見分けて、必要なら検索で探せるようになる。

## 背景

束の親 [#322](https://github.com/shuhei1101/dev-docs/issues/322) の要望で、子 [#321](https://github.com/shuhei1101/dev-docs/issues/321)・[#318](https://github.com/shuhei1101/dev-docs/issues/318) を 1 つの作業 PR で対応する。

- #321: [shuhei1101/project-index#268](https://github.com/shuhei1101/project-index/pull/268) で、配信元の設定の `direct_commit.kinds[]` に `{id, body: false}` を記載した種類は本文の直コミットを断り、書き込みの API が 422 を返却するようになった。断る種類は読み取り API の `GET /sources/{source}/config` の `directCommit.metadataOnlyKinds` で返却される（[shuhei1101/project-index#280](https://github.com/shuhei1101/project-index/pull/280)）。dev-docs のメタデータの画面は直コミットできるかを端末の設定の `directCommit.writeApiKinds` だけで決めていて、`metadataOnlyKinds` を使用していない
- #318: [shuhei1101/project-index#265](https://github.com/shuhei1101/project-index/pull/265) で、`documents[].search_exclude` に該当する文書は文書の一覧で `excluded: true` を持ち、検索では既定で除かれて件数が `excludedCount` に入り、`include_excluded=true` で返却されるようになった。dev-docs の画面はこれらを使用していない

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.mark.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.mark.md) | 画面の計画書 |
