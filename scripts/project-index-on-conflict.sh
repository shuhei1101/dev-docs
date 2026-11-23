#!/usr/bin/env bash
# project-index の書き込みの API が衝突して修正を残したブランチをリモートへプッシュし、
# コミットするブランチへの PR を作成して、PR の URL を標準出力の最後の行に出すスクリプト。
# project-index の端末の設定の sources[].direct_commit.on_conflict.command から、クローン本体を作業ディレクトリにして実行される。
#
#   PROJECT_INDEX_CONFLICT_BRANCH=project-index/conflict/20261123-103000-0a1b2c3 PROJECT_INDEX_TARGET_BRANCH=develop PROJECT_INDEX_COMMIT_MESSAGE='タグを修正する' PROJECT_INDEX_SOURCE=dev-docs PROJECT_INDEX_BASE_COMMIT=0a1b2c3 bash scripts/project-index-on-conflict.sh
set -euo pipefail

# 必須の環境変数（どれかが空なら 2 で終わる）
required=(
    PROJECT_INDEX_CONFLICT_BRANCH
    PROJECT_INDEX_TARGET_BRANCH
    PROJECT_INDEX_COMMIT_MESSAGE
    PROJECT_INDEX_SOURCE
    PROJECT_INDEX_BASE_COMMIT
)
missing=()
for name in "${required[@]}"; do
    if [ -z "${!name:-}" ]; then
        missing+=("$name")
    fi
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "必須の環境変数がありません: ${missing[*]}" >&2
    exit 2
fi

# 残したブランチをリモートへプッシュする（失敗したら git の終了コードで終わる）
set +e
git push origin -- "$PROJECT_INDEX_CONFLICT_BRANCH" 1>&2
status=$?
set -e
if [ "$status" -ne 0 ]; then
    echo "ブランチ ${PROJECT_INDEX_CONFLICT_BRANCH} をプッシュできませんでした" >&2
    exit "$status"
fi

# コミットするブランチへの PR を作成する（ラベルは付けない）
body="メタデータの画面の直コミットがほかの変更と衝突したため、修正をこのブランチに残しました。

- 配信元: ${PROJECT_INDEX_SOURCE}
- 編集を始めたときのコミット: ${PROJECT_INDEX_BASE_COMMIT}"
set +e
output="$(gh pr create \
    --base "$PROJECT_INDEX_TARGET_BRANCH" \
    --head "$PROJECT_INDEX_CONFLICT_BRANCH" \
    --title "$PROJECT_INDEX_COMMIT_MESSAGE" \
    --body "$body")"
status=$?
set -e
if [ "$status" -ne 0 ]; then
    exit "$status"
fi

# gh の標準出力の空でない最後の行（PR の URL）を最後の行に出す
url="$(printf '%s\n' "$output" | sed '/^[[:space:]]*$/d' | tail -n 1)"
echo "$url"
