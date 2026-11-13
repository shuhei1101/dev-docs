# 判定フローチャートの YAML から GitHub Pages の公開ページを生成し、2 文書を「使い方」へ戻す

## 概要

利用者が、GitHub Pages の「使い方」から判定フローチャートの 2 文書（新しく作るか修正するかの判定・documentsの行の判定）を読めるようになる。

## 背景

[Issue #173](https://github.com/shuhei1101/dev-docs/issues/173) の要望。
[PR #171](https://github.com/shuhei1101/dev-docs/pull/171) で 2 文書を `docs/guide/` の Markdown から `docs/flowchart/` の YAML に変換し、Pages から除外した（PR #171 の確認ログのユーザーの回答）。
Pages は `develop` の `/docs` を Jekyll でそのまま描く legacy のビルドで、YAML から Markdown を生成する手段を持たないため、2 文書は公開ページから消えている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、決める工程へ持ち越すビルドの方式 |
