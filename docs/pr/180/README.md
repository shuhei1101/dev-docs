# PR #101・#136 の反映作業の一覧の確認方法の値を引用符で囲み、YAML として読めるようにする

## 概要

PR #101・#136 の反映作業の一覧（`反映作業/index.yaml`）を YAML として解析できるようにし、tester がリリースのときに反映作業を集約できるようにする。

## 背景

[Issue #159](https://github.com/shuhei1101/dev-docs/issues/159) の要望。
[PR #155](https://github.com/shuhei1101/dev-docs/pull/155) のマージ提案のレビューで、[PR #101](https://github.com/shuhei1101/dev-docs/pull/101) の反映作業の一覧の `確認方法` の値が「コロン + 空白」を含むため YAML として解析できない（`mapping values are not allowed here`）ことが見つかった。
develop の反映作業の一覧を全て解析したところ、[PR #136](https://github.com/shuhei1101/dev-docs/pull/136) の一覧も `確認方法` の値（`format: json`・`loading: false`）で同じく解析できない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
