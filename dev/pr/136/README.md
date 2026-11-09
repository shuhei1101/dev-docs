# サーバーの起動直後の MCP の要求と、読み込みの後の管理の MCP の status が時間切れより十分短く応答するよう修正する

## 概要

エージェントが、dev-docs のサーバーを起動・再起動した直後と配信元の読み込みの後に、文書の MCP と管理の MCP の `status` を時間切れせずに使用できるようになる。

## 背景

[Issue #135](https://github.com/shuhei1101/dev-docs/issues/135) は次の 2 件の束。

- [#123](https://github.com/shuhei1101/dev-docs/issues/123): 起動した直後、全ての配信元の読み込みが終わるまで文書の MCP の全てのツールが待つ。[PR #120](https://github.com/shuhei1101/dev-docs/pull/120) の計測では読み込みに約 6 分かかり、その間の作業範囲の外の配信元への `search_docs` が時間切れになった
- [#126](https://github.com/shuhei1101/dev-docs/issues/126): 読み込みが終わった後、管理の MCP の `status` が配信中の全ての配信元に `check_sync` をかけ、200 秒を超えても応答しない

読み込みを待ち受けの裏へ回し、配信元を参照する要求を読み込みの終わりまで待たせる方式は [PR #76](https://github.com/shuhei1101/dev-docs/pull/76)（#65）で入れた。
[#114](https://github.com/shuhei1101/dev-docs/issues/114)（project-index への切り出し）の依存として着手する（[#1 の回答](https://github.com/shuhei1101/dev-docs/issues/1#issuecomment-6728772279)、案 A）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
