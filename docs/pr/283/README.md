# 公開ページの配信の workflow（pages.yml）のインターフェース定義と E2E テストを作成する

## 概要

開発者とエージェントが、公開ページの配信の workflow `.github/workflows/pages.yml` の入力・制約・フローをインターフェース定義で参照でき、フローごとの E2E テストで振る舞いを確認できるようになる。

## 背景

[Issue #268](https://github.com/shuhei1101/dev-docs/issues/268) の要望。
[.github/workflows/pages.yml](https://github.com/shuhei1101/dev-docs/blob/8abfaee/.github/workflows/pages.yml)（develop への push と `workflow_dispatch` で、公開の文書を 1 枚の HTML にまとめて GitHub Pages へ配信する workflow）に、インターフェース定義（`docs/interface/` の `entry.kind: trigger` の設計書）と E2E テストが無い。
テストを回す workflow は、[PR #261](https://github.com/shuhei1101/dev-docs/pull/261)（起点 [Issue #198](https://github.com/shuhei1101/dev-docs/issues/198)）でインターフェース定義 [IF-155-26](https://github.com/shuhei1101/dev-docs/blob/8abfaee/docs/interface/IF-155-26.yaml) と [tests/e2e/workflow/conftest.py](https://github.com/shuhei1101/dev-docs/blob/8abfaee/tests/e2e/workflow/conftest.py) の E2E テストの fixture を持った。
#261 では要望に含まれないためスコープ外にしていた。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 公開ページの配信の workflow のインターフェース定義と E2E テストの計画書 |
| [反映作業](./反映作業/index.yaml) | マージの後の公開ページの配信の確認 |
