# 文書とソースコードの索引・検索・書き込みの MCP を project-index へ切り出し、配信元の設定の既定のファイル名を project-index.yaml にする

## 概要

画面を使わない端末や CI でも、文書とソースコードの索引・検索・書き込みの MCP を、画面のサーバーの依存なしに入れられるようにする。
各プロジェクトに配置する配信元の設定の既定のファイル名を、複数のツールが参照することが分かる `project-index.yaml`・`project-index.local.yaml` にする。

## 背景

[Issue #114](https://github.com/shuhei1101/dev-docs/issues/114) の要望。
dev-docs は画面のサーバー（React の画面・mdmark の描画）と、文書の MCP（`search_docs`・`trace_related`・`list_changes`・`write_docs` など）・配信元の読み込みを 1 つのリポジトリ・プラグイン・サーバーで持っており、検索の MCP だけを使用する端末でも画面の依存ごと入れる必要がある。
切り出し先の [shuhei1101/project-index](https://github.com/shuhei1101/project-index) は、ユーザーが作成し、立ち上げ Issue [project-index#2](https://github.com/shuhei1101/project-index/issues/2) で土台（起動の入口・設計書の骨格・プラグインの定義）ができている。
依存の [#112](https://github.com/shuhei1101/dev-docs/issues/112)・[#107](https://github.com/shuhei1101/dev-docs/issues/107)・[#113](https://github.com/shuhei1101/dev-docs/issues/113)・[#119](https://github.com/shuhei1101/dev-docs/issues/119) は closed。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインの計画書 |
| [画面](./画面.md) | 画面の計画書 |
