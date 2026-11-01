"""`POST /_admin/session-context` の本文と応答の型と、文脈の文の字数の上限・プロンプトの ID。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `context` の字数の上限
CONTEXT_MAX_CHARS = 1000
# 返し済みの記録を削除する `reason`
FORGET_REASONS = frozenset({"clear", "compact"})

# 文脈の文を描画するプロンプトの YAML（`content/prompts/session-context.yaml`）の ID
SESSION_CONTEXT_PROMPT_ID = "session-context"


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
    loading: bool = Field(
        default=False, description="配信元の初回の読み込みが終わっていないとき `true`"
    )
