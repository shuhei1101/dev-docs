# 管理用プラグインのスキル（setup・global-setup）の文言を、AI slop の単語の対応表に合わせて修正する

## 概要

管理用プラグインのスキル `setup`・`global-setup` の `SKILL.md` の文言を、knowledge の AI slop の単語の対応表に合わせて修正する。

## 背景

[Issue #149](https://github.com/shuhei1101/dev-docs/issues/149) の要望。
[PR #148](https://github.com/shuhei1101/dev-docs/pull/148)（起点 [Issue #144](https://github.com/shuhei1101/dev-docs/issues/144)）の現状調査で、`templates/files.schema.yaml` の `description` と同じ文（「どんなときに読むか」）を `setup/SKILL.md` が持っているのが見つかった。
[PR #147](https://github.com/shuhei1101/dev-docs/pull/147)（フックが返却する文言）・PR #148（`templates/`）・#95（文書の移行）はスキルを対象にしていない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [管理用プラグイン](./管理用プラグイン.md) | 管理用プラグインの計画書 |
