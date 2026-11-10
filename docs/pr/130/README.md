# 設計書の `decisions`（検討事項の ID）を、変換で話し合いの記録の検討事項へのリンクにする

## 概要

利用者が、設計書の `decisions` に記載した検討事項の ID を、画面で話し合いの記録の検討事項へのリンクとして参照できるようになる。

## 背景

[#129](https://github.com/shuhei1101/dev-docs/issues/129) の要望。
[shuhei1101/ai-monitor#3222](https://github.com/shuhei1101/ai-monitor/pull/3222) で、設計書のスキーマの `refs` を持つ場所に、検討事項の ID の配列 `decisions`（例 `D-313`）が追加された。
dev-docs のスキーマ駆動の変換（`features/convert/markdown.py`）は `decisions` を扱わず、文字列の並びのまま出す。`link_reference`（`features/convert/inline.py`）は同じ配信元の文書の ID だけをリンクにするため、`D-313` はリンクにならない。
規約『表し方の優先順位』の hidden-content-02 は、検討事項の ID を文の中に記載せず、関連のキーに移してリンクで出すと定めている。

[#128](https://github.com/shuhei1101/dev-docs/pull/128)（起点 [#118](https://github.com/shuhei1101/dev-docs/issues/118)）のスコープ外から切り出した作業。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [反映作業](./反映作業/index.yaml) | マージの後のサーバーの再起動 |
