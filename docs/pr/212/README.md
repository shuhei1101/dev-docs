# Mermaid の図の click の id: の参照をリンクへ解き、比較中の右側の目次に変更のマーカーを出し、migrate が outside_read で送信して project-index のサーバーのバージョンを確認する

## 概要

利用者が、文書の画面で手で記載した Mermaid の図（クラス図など）のノードから、`click` の `id:` の参照が指す文書のページへ移れるようになる。
利用者が、文書の画面で 2 つのリビジョンを比べているときに、mdmark の右側の目次で変わったセクションを見分けられるようになる。
利用者が、`dev-docs migrate --project-index` で dev-docs の端末の設定の `sources[]` を project-index の端末の設定へ移せるようになる。

## 背景

[Issue #209](https://github.com/shuhei1101/dev-docs/issues/209) は、[#196](https://github.com/shuhei1101/dev-docs/issues/196)・[#199](https://github.com/shuhei1101/dev-docs/issues/199)・[#202](https://github.com/shuhei1101/dev-docs/issues/202)・[#203](https://github.com/shuhei1101/dev-docs/issues/203) をまとめた親の Issue。

- #196: 移し替えの手順（`schemas/conversions/v0.4.0.py`）は `click` の href を `id:` の参照へ書き換えるが、画面の変換（`diagrams.py` の `render_mermaid`）は読み取れない Mermaid の図をそのまま出力し、参照を解かない。mdmark は Mermaid を `securityLevel: "strict"` で描くため、`click` はそのままでは働かない。依頼元は [shuhei1101/project-index#70](https://github.com/shuhei1101/project-index/pull/70)
- #199: [#88](https://github.com/shuhei1101/dev-docs/issues/88)（[PR #174](https://github.com/shuhei1101/dev-docs/pull/174)）で独自の目次を削除し、比較中の変わったセクションのマーカーが出なくなった。mdmark は [shuhei1101/mdmark#550](https://github.com/shuhei1101/mdmark/pull/550) で右側の目次にマーカーを出すようになり、`v0.13.0` に入った。画面が参照する mdmark は `v0.11.0`
- #202: [#164](https://github.com/shuhei1101/dev-docs/issues/164) の作業 PR [#183](https://github.com/shuhei1101/dev-docs/pull/183) の反映作業「端末の設定の移し替え」は、`expectedVersion` を受け付けない古いバージョンの project-index のサーバーへ保存して 400 で止まった（[報告](https://github.com/shuhei1101/dev-docs/issues/164#issuecomment-6852784537)）。疎通確認はサーバーのバージョンを確認していない
- #203: project-index のサーバーを起動し直した後も、`_sent_row` が行の外部の読み取りを `outsideRead` で送信し、`outside_read` だけを受け付ける `PUT /settings/sources` に 400 で断られた（[報告](https://github.com/shuhei1101/dev-docs/issues/164#issuecomment-6875446039)）。#164 は close し、止まった反映作業 2 件はこの作業 PR の反映作業へ移った（[#164 の close の依頼](https://github.com/shuhei1101/dev-docs/issues/164#issuecomment-6875671912)）

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [画面](./画面.md) | 画面の計画書 |
