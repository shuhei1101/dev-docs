"""`nav` の `auto` の `filter` の条件の木と、見出しの型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Condition(BaseModel):
    """1 つの項目を比べる条件。"""

    model_config = ConfigDict(extra="forbid")

    field: str
    op: Literal[
        "eq",
        "ne",
        "prefix",
        "suffix",
        "contains",
        "not_contains",
        "regex",
        "glob",
        "gt",
        "gte",
        "lt",
        "lte",
        "exists",
        "not_exists",
    ] = Field(
        description=(
            "比べ方。regex は値の各行に適用する"
            "（^・$ は各行の先頭・末尾。値全体の先頭・末尾は \\A・\\Z）。"
            "glob は値全体に適用し、** は / をまたぎ、*・? は / をまたがない"
        )
    )
    values: list[str] = Field(default_factory=list)
    match: Literal["any", "all"] = "any"
    case_sensitive: bool = Field(
        default=False,
        description=(
            "False は NFKC と casefold をした後に比べる"
            "（regex はパターンに正規化をかけず、re.IGNORECASE と NFKC にした値で比べる）"
        ),
    )


class Group(BaseModel):
    """条件を AND・OR でまとめるか、否定する。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all_of: list[Condition | Group] | None = Field(default=None, alias="and")
    any_of: list[Condition | Group] | None = Field(default=None, alias="or")
    not_: Condition | Group | None = Field(
        default=None,
        alias="not",
        description="中の条件か束に該当しない文書に該当する。and・or の中にも配置できる",
    )


@dataclass(frozen=True)
class Heading:
    """Markdown の本文の見出し 1 つ。"""

    # 本文の行番号（1 始まり）
    line: int
    # `#` の数（1〜6）
    level: int
    # `#` と前後の空白、末尾の閉じの `#` を除いた文字列
    text: str
