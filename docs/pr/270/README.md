# 配信元 dev-docs の配信の設定を見直す: タブの並びとサイドバーのグループ・検索の対象とメタデータ

## 概要

開発ドキュメントサーバーの画面で、配信元 dev-docs のタブとサイドバーを決まりどおりに並べ、コード・テストも検索と関連のたどりの対象にする。

## 背景

束の親 [Issue #269](https://github.com/shuhei1101/dev-docs/issues/269) の要望で、次の 2 件を 1 つの作業 PR で対応する。

- [Issue #229](https://github.com/shuhei1101/dev-docs/issues/229): タブが 17 件で画面の幅に収まらず、並びに決まりが無い。フォルダの目次（`index`）もタブとサイドバーに並ぶ。決まりは [shuhei1101/knowledge#421](https://github.com/shuhei1101/knowledge/issues/421) で規約『開発ドキュメントのナビゲーション』（`dev-docs-navigation`）として登録された
- [Issue #257](https://github.com/shuhei1101/dev-docs/issues/257): 検索の対象（`project-index.yaml` の `documents[]`）とメタデータが、project-index の setup の推奨の範囲（`**/*`）と付け方より前のまま。`src/dev_docs/`・`frontend/src/`・`tests/` のコードが対象に入っていない。直下と `docs/` 直下のファイルを管理用の YAML に記載できるようにする [shuhei1101/project-index#133](https://github.com/shuhei1101/project-index/issues/133) は close 済み

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、子 Issue ごとの終わりの条件 |
| [反映作業](./反映作業/index.yaml) | マージの後に設定を配信へ入れる作業 |
