# AI Monitor v0.5.0 の配布物へ追従する

## 概要

dev-docs が、AI Monitor v0.5.0 の配布物（規約・テンプレート・配布先の反映作業）に追従した状態になる。

## 背景

[Issue #243](https://github.com/shuhei1101/dev-docs/issues/243) の要望。
AI Monitor が v0.5.0 のタグを打ち、配布物リストの分類ごとの配布先の行動と、配布先の反映作業『配布先の mdmark の設定へのノードの種類の記載』（[shuhei1101/ai-monitor#3462](https://github.com/shuhei1101/ai-monitor/pull/3462)）が届いた。
前提の v0.4.0 への追従（[#224](https://github.com/shuhei1101/dev-docs/issues/224)）は [#256](https://github.com/shuhei1101/dev-docs/pull/256) でマージ済みで、develop の `ai-monitor-version.ini` は `v0.4.0`、直下に `mdmark.config.yaml` は無い。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と、v0.4.0..v0.5.0 で変わった配布物の dev-docs への当て方 |
| `反映作業/index.yaml` | 配布先の反映作業の一覧。作業ごとのフォルダに、配布元からコピーしたスクリプトと `dry-run.log` を配置する |
