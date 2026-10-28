"""`POST /_admin/session-context` の本文と応答の型と、文脈に入れる使い方の文。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `context` の字数の上限
CONTEXT_MAX_CHARS = 2000
# 返し済みの記録を削除する `reason`
FORGET_REASONS = frozenset({"clear", "compact"})

# 配信元の一覧の後に置く、場面ごとの短い使い方
SESSION_USAGE = """使い方:
- 始めに `describe(source)` で種類・タグ・書き方を確かめる
- 探すときは `search_docs`。全体を見るときは `group_by="tags"`、配信元をまたぐときは `source="*"`、本文まで読むときは `view="full"`
- 前に読んだ後の変更は `list_changes` で確かめる
- 範囲のファイルを作った・消した・改名したら、管理用の YAML の行を修正する"""

# 使える配信元が 0 件のときの文
SETUP_GUIDE = (
    "この作業場所から使える dev-docs の配信元はありません。"
    "配信元にするときは `/dev-docs:setup` を実行します。"
)


class SessionContextRequest(BaseModel):
    """SessionStart のフックが送信する本文。"""

    # フックの入力に増えたキーを断らないよう、知らないキーは捨てる
    model_config = ConfigDict(extra="ignore")

    cwd: str = Field(description="セッションの作業場所の絶対パス")
    session_id: str | None = Field(default=None, description="Claude Code のセッション ID")
    agent_id: str | None = Field(default=None, description="サブエージェントの ID")
    reason: Literal["startup", "resume", "clear", "compact", "fork"] = Field(
        default="startup", description="SessionStart の入力の `source`"
    )


class ContextSource(BaseModel):
    """応答の `sources[]` の 1 行。"""

    id: str = Field(description="配信元の ID")
    access: Literal["read_write", "read"] = Field(description="権限")


class SessionContextResponse(BaseModel):
    """フックが文脈に入れる文と内訳。"""

    context: str = Field(description="文脈の文")
    sources: list[ContextSource] = Field(description="作業場所から使える配信元")
    warnings: list[str] = Field(description="同期のずれ・古い設定・配信していない配信元")
    forgotten: bool = Field(description="返し済みの記録を削除したか")
