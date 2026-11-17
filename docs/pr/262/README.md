# 画面の不具合を修正する: 配信元の 1 回目の表示・nav の auto.filter の共通のキー・Mermaid の click のリンク

## 概要

利用者が dev-docs の画面で、配信元を 1 回目に開いても短い時間で文書を参照でき、共通のキーで絞り込んだタブに文書が並び、Mermaid の図の `click` のノードから同じ配信元の文書を開ける。

## 背景

束の親 [Issue #259](https://github.com/shuhei1101/dev-docs/issues/259) の要望。同じ種類（`kind:不具合の修正`）の次の Issue を 1 つの作業 PR で扱う。

| Issue | 背景 |
| --- | --- |
| [#225](https://github.com/shuhei1101/dev-docs/issues/225) | 配信元を選んでも表示に時間がかかる・表示できないことがある。[#230](https://github.com/shuhei1101/dev-docs/pull/230) で 2 回目以降の短縮と表示できない理由の警告が入り、1 回目の遅さは [shuhei1101/project-index#85](https://github.com/shuhei1101/project-index/issues/85) で扱うと決定した（[確認ログ](https://github.com/shuhei1101/dev-docs/pull/230#discussion_r4579519925)）。project-index#85 は close 済みで、残りは 1 回目の表示の確認 |
| [#249](https://github.com/shuhei1101/dev-docs/issues/249) | nav の `auto.filter` に行の `metadata` で対応付けた共通のキー（`category`）を記載すると、project-index は受け付けるが画面はタブを空にする。shuhei1101/observability は `page` で 1 件ずつ並べる回避を取っている |
| [#255](https://github.com/shuhei1101/dev-docs/issues/255) | mdmark の develop の最新で、結合テスト `body_mermaid_click_link`（[#212](https://github.com/shuhei1101/dev-docs/pull/212) で追加）が Mermaid の `click` のノードを `<a>` として見つけられず fail する |

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理・変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.md) | 画面の計画書 |
