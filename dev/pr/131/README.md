# Git 管理外の配信元の設定を先頭に置いても読めるようにし、端末の設定と状態の置き場を XDG に揃える

## 概要

利用者が、Git 管理外のフォルダの `dev-docs.yaml` と、`.gitignore` した `dev-docs.local.yaml` のどちらを配信元の設定の先頭に置いても配信でき、端末の設定と状態の置き場を `XDG_CONFIG_HOME`・`XDG_STATE_HOME`・`DEV_DOCS_STATE_DIR` で決められるようになる。

## 背景

[#112](https://github.com/shuhei1101/dev-docs/issues/112) の要望。
配信元の設定（`sources[].config`）の先頭のファイルは `default_ref` のリビジョンから読むため、先頭が Git 管理下で `.gitignore` したファイルだと「`develop` に `dev-docs.local.yaml` がありません」で配信できない。
端末の設定は `~/.config/dev-docs/settings.yaml`、状態は `~/.local/state/dev-docs` に固定で、`XDG_CONFIG_HOME`・`XDG_STATE_HOME` を参照しない。
同じ決定で、rule-inject・alias-inject・mdmark・knowledge も既定のパスと環境変数の名前を統一する。

[#114](https://github.com/shuhei1101/dev-docs/issues/114)（project-index への切り出し）の依存として着手する。
進行中の [PR #101](https://github.com/shuhei1101/dev-docs/pull/101) が同じ `src/dev_docs/features/sources/service.py` を変更していて、競合は後にマージする側で解消する。
[#141](https://github.com/shuhei1101/dev-docs/issues/141)（反映作業の判定の `started` への差し替えと、待ちのスクリプトのログの置き場の XDG への統一）もこの PR で解消し、マージの後に閉じる。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインの計画書 |
| [反映作業](./反映作業/index.yaml) | マージの後のサーバーの再起動 |
