# AI Monitor v0.4.0 の配布物へ追従する

## 概要

dev-docs が、AI Monitor v0.4.0 の配布物（規約・設計書のスキーマ・配布先の反映作業）に追従した状態になる。

## 背景

[Issue #224](https://github.com/shuhei1101/dev-docs/issues/224) の要望。
AI Monitor が v0.4.0 のタグを打ち（[shuhei1101/ai-monitor#3447](https://github.com/shuhei1101/ai-monitor/issues/3447) は close 済み）、配布物リストの分類ごとの配布先の行動と、配布先の反映作業が届いた。
[扱いの判断](https://github.com/shuhei1101/dev-docs/issues/224#issuecomment-6889319278) で [#74](https://github.com/shuhei1101/dev-docs/issues/74) をこの Issue へ統合した。
develop の `ai-monitor-version.ini` は `v0.3.0` のまま、`schemas/` に AI Monitor から配られたスキーマのコピーがあり、`project-index.yaml` の設計書の行はそのコピーを指している。
`docs/architecture/ARCH-155-1.yaml` には、v0.4.0 の変換が落とす `line: reply` が 2 か所残っている（削除を依頼した [#161](https://github.com/shuhei1101/dev-docs/issues/161) の PR [#181](https://github.com/shuhei1101/dev-docs/pull/181) はマージされずに閉じた）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| `反映作業/index.yaml` | 配布先の反映作業の一覧。作業ごとのフォルダに、配布元からコピーしたスクリプトと `dry-run.log` を配置する |
