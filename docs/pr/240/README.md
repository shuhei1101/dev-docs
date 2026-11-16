# mdmark の参照を既定で develop の最新にし、設定でバージョンを固定できるようにする

## 概要

dev-docs が mdmark を、既定では mdmark の develop の最新で参照し、設定で特定のバージョン（タグ・commit）に固定できるようにする。

## 背景

[Issue #236](https://github.com/shuhei1101/dev-docs/issues/236) の要望。
画面が読み込む mdmark（`use-mdmark.ts` の jsDelivr の URL）・`package.json` の `devDependencies`・公開ページのビルド（`scripts/build_pages.py` の `MDMARK_TAG`）が `v0.13.0` に固定されていて、mdmark の develop へ入った機能をタグが打たれるまで使えない。
作業 PR [#212](https://github.com/shuhei1101/dev-docs/pull/212) が mdmark のタグ（[shuhei1101/mdmark#571](https://github.com/shuhei1101/mdmark/issues/571)）を待って止まり、それを待つ他のリポジトリの作業 PR まで止まった。
mdmark の側で develop の最新を参照できるようにする作業は [shuhei1101/mdmark#620](https://github.com/shuhei1101/mdmark/issues/620) が持つ。
未着手だった [#228](https://github.com/shuhei1101/dev-docs/issues/228) を統合している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [画面](./画面.md) | 画面の計画書（mdmark の読み込み先） |
| [開発ドキュメントサーバー](./開発ドキュメントサーバー.md) | 開発ドキュメントサーバーの計画書（設定のキー・画面への受け渡し・公開ページのビルド・開発の依存） |
