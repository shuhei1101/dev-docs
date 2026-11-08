from __future__ import annotations

import json
import re
from typing import Any

import pytest

from dev_docs.features.convert.diagrams import er_table_titles, render_diagram, render_mermaid
from dev_docs.features.convert.types import DiagramHead

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")


def _definition(block: str, marker: str) -> dict[str, Any]:
    """部品の範囲から定義の JSON を取り出す。"""
    match = re.search(
        rf"<!-- {marker} -->\n\n```json\n(.*?)\n```\n\n<!-- /{marker} -->", block, re.S
    )
    assert match is not None, block
    definition: dict[str, Any] = json.loads(match.group(1))
    return definition


def _node(definition: dict[str, Any], node_id: str) -> dict[str, Any]:
    """フロー図の定義から `id` のノードを取り出す。"""
    node: dict[str, Any] = next(n for n in definition["nodes"] if n["id"] == node_id)
    return node


def test_render_diagram() -> None:
    """フローチャート（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    definition = _definition(result, "flow")
    assert (definition["title"], definition["scope"], definition["updated"]) == (
        "図",
        "文書",
        "2026-11-03",
    )
    assert [node["name"] for node in definition["nodes"]] == ["A", "B"]
    assert [(wire["label"], wire["line"]) for wire in definition["wires"]] == [("x", "flow")]
    assert "```mermaid" not in result


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        pytest.param("actor", "external", id="actor"),
        pytest.param("external", "external", id="external"),
        pytest.param("process", "script", id="process"),
        pytest.param("system", "script", id="system"),
        pytest.param("store", "data", id="store"),
        pytest.param("start", "start", id="start"),
        pytest.param("question", "question", id="question"),
        pytest.param("action", "action", id="action"),
        pytest.param("result", "result", id="result"),
        pytest.param(None, "script", id="none"),
    ],
)
def test_render_diagram_when_node_kinds(kind: str | None, expected: str) -> None:
    """ノードの種類（正常系）。"""
    # 準備
    node: dict[str, Any] = {"id": "a"}
    if kind is not None:
        node["kind"] = kind
    # 実行
    result = render_diagram({"nodes": [node], "edges": []}, "flowchart", HEAD)
    # 検証
    assert _node(_definition(result, "flow"), "a")["kind"] == expected


def test_render_diagram_when_shape_only() -> None:
    """古いキーの `shape` だけを持つノード（正常系）。"""
    # 準備
    value = {"nodes": [{"id": "a", "shape": "diamond"}], "edges": []}
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    assert _node(_definition(result, "flow"), "a")["kind"] == "script"


def test_render_diagram_when_hint_and_tip() -> None:
    """ノードの説明と線の種類・詳細（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A", "hint": "説明"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "読む", "line": "read", "tip": "詳細"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    definition = _definition(result, "flow")
    assert _node(definition, "a")["hint"] == "説明"
    wire = definition["wires"][0]
    assert (wire["line"], wire["label"], wire["tip"]) == ("read", "読む", "詳細")


def test_render_diagram_when_unknown_line() -> None:
    """`LINE_KINDS` に無い線の種類（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b", "line": "dotted"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    assert _definition(result, "flow")["wires"][0]["line"] == "flow"


@pytest.mark.parametrize(
    ("kind", "direction", "expected"),
    [
        pytest.param("flowchart", None, "TD", id="flowchart"),
        pytest.param("dataflow", None, "LR", id="dataflow"),
        pytest.param("architecture", None, "LR", id="architecture"),
        pytest.param("dataflow", "TD", "TD", id="dataflow-td"),
    ],
)
def test_render_diagram_when_direction(kind: str, direction: str | None, expected: str) -> None:
    """向きの既定と指定（正常系）。"""
    # 準備
    value: dict[str, Any] = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b"}],
    }
    if direction is not None:
        value["direction"] = direction
    # 実行
    result = render_diagram(value, kind, HEAD)  # type: ignore[arg-type]
    # 検証
    definition = _definition(result, "flow")
    a, b = _node(definition, "a"), _node(definition, "b")
    # 先のノードが下にあれば上から下、右にあれば左から右
    actual = "TD" if b["y"] > a["y"] else "LR"
    assert actual == expected


def test_render_diagram_when_frame() -> None:
    """枠（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [],
        "frame": {"label": "判定", "nodes": ["a", "b"]},
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    definition = _definition(result, "flow")
    frame = definition["frame"]
    assert frame["title"] == "判定"

    def inside(node: dict[str, Any]) -> bool:
        return bool(
            frame["x"] <= node["x"]
            and frame["y"] <= node["y"]
            and node["x"] + node["w"] <= frame["x"] + frame["w"]
            and node["y"] + node["h"] <= frame["y"] + frame["h"]
        )

    assert inside(_node(definition, "a"))
    assert inside(_node(definition, "b"))
    assert not inside(_node(definition, "c"))


def _wires(definition: dict[str, Any]) -> list[tuple[str, str, str]]:
    """フロー図の定義の線の元・先・種類の組。"""
    return [(w["from"], w["to"], w["line"]) for w in definition["wires"]]


def test_render_diagram_when_state() -> None:
    """状態遷移（正常系）。"""
    # 準備
    value = {
        "initial": "下書き",
        "final": ["公開"],
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "transitions": [
            {"from": "下書き", "to": "公開", "trigger": "公開する", "condition": "承認済み"},
            {"from": "公開", "to": "公開", "trigger": "更新する"},
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    definition = _definition(result, "flow")
    assert [(n["id"], n["kind"], n["name"]) for n in definition["nodes"]] == [
        ("start", "start", "開始"),
        ("s1", "action", "下書き"),
        ("s2", "action", "公開"),
        ("end", "result", "終了"),
    ]
    assert _wires(definition) == [
        ("start", "s1", "flow"),
        ("s1", "s2", "flow"),
        ("s2", "s2", "loop"),
        ("s2", "end", "flow"),
    ]
    assert definition["wires"][1]["label"] == "公開する [承認済み]"


def test_render_diagram_when_state_representative() -> None:
    """どの状態からも入る遷移と元の状態へ戻る遷移（正常系）。"""
    # 準備
    value = {
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "transitions": [
            {"from": "全状態", "to": "下書き", "representative": "公開"},
            {"from": "下書き", "to": "元の状態", "representative": "公開"},
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    definition = _definition(result, "flow")
    names = [n["name"] for n in definition["nodes"]]
    assert "全状態" not in names
    assert "元の状態" not in names
    assert [(w["from"], w["to"]) for w in definition["wires"]] == [("s2", "s1"), ("s1", "s2")]


CUSTOMERS = {
    "name": "customers",
    "title": "顧客",
    "summary": "注文する人",
    "columns": [
        {"name": "id", "title": "顧客 ID", "type": "bigint", "primary_key": True, "not_null": True},
        {"name": "email", "title": "メール", "type": "text"},
    ],
}


def _table(definition: dict[str, Any], table_id: str) -> dict[str, Any]:
    """ER 図の定義から `id` のテーブルを取り出す。"""
    table: dict[str, Any] = next(t for t in definition["tables"] if t["id"] == table_id)
    return table


def _columns(table: dict[str, Any]) -> list[tuple[str, bool, bool, bool]]:
    """テーブルの列の名前と `pk`・`fk`・`nn` の組。"""
    return [
        (column["name"], bool(column.get("pk")), bool(column.get("fk")), bool(column.get("nn")))
        for column in table["columns"]
    ]


def test_render_diagram_when_er() -> None:
    """ER 図（正常系）。"""
    # 準備
    value = {
        "entities": [
            {"name": "顧客"},
            {
                "name": "注文",
                "columns": [
                    {"type": "bigint", "name": "id", "key": "PK"},
                    {"type": "bigint", "name": "customer_id", "key": "FK"},
                ],
            },
        ],
        "relations": [
            {
                "from": "顧客",
                "from_column": "id",
                "from_cardinality": "1",
                "to": "注文",
                "to_column": "customer_id",
                "to_cardinality": "0..n",
                "label": "注文する",
            }
        ],
    }
    # 実行
    result = render_diagram(value, "er", HEAD, tables=[CUSTOMERS])
    # 検証
    definition = _definition(result, "er")
    assert _table(definition, "顧客")["name"] == "customers"
    assert _columns(_table(definition, "顧客")) == [
        ("id", True, False, True),
        ("email", False, False, False),
    ]
    assert _columns(_table(definition, "注文")) == [
        ("id", True, False, False),
        ("customer_id", False, True, False),
    ]
    assert definition["relations"] == [
        {
            "from": "顧客",
            "fromColumn": "id",
            "fromCard": "1",
            "to": "注文",
            "toColumn": "customer_id",
            "toCard": "0..n",
            "label": "注文する",
        }
    ]
    assert "```mermaid" not in result


# 顧客の id から商品への関連の両端（パラメータごとに一部を差し替える）
RELATION = {
    "from": "顧客",
    "from_column": "id",
    "from_cardinality": "1",
    "to": "商品",
    "to_column": "product_id",
    "to_cardinality": "0..n",
}


@pytest.mark.parametrize(
    ("relation", "entities"),
    [
        pytest.param(RELATION, [{"name": "商品"}], id="missing-column"),
        pytest.param(
            {**RELATION, "to_column": "id", "to_cardinality": "many"},
            [{"name": "商品", "columns": [{"type": "int", "name": "id"}]}],
            id="unknown-cardinality",
        ),
        pytest.param(
            {"from": "顧客", "to": "商品", "cardinality": "||--o{"},
            [{"name": "商品", "columns": [{"type": "int", "name": "id"}]}],
            id="old-cardinality",
        ),
        pytest.param({**RELATION, "to": "無い実体", "to_column": "id"}, [], id="missing-entity"),
    ],
)
def test_render_diagram_when_er_excluded(
    relation: dict[str, Any], entities: list[dict[str, Any]]
) -> None:
    """図に出さない関連（正常系）。"""
    # 準備
    value = {
        "entities": [{"name": "顧客", "columns": [{"type": "int", "name": "id"}]}, *entities],
        "relations": [relation],
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    assert _definition(result, "er")["relations"] == []


def test_render_diagram_when_er_layout() -> None:
    """格子の配置（正常系）。"""
    # 準備
    columns = [{"type": "int", "name": "a"}, {"type": "int", "name": "b"}]
    value = {
        "entities": [
            {"name": "t0", "columns": columns},
            {"name": "t1", "columns": columns},
            {"name": "t2", "columns": columns},
            {"name": "t3", "columns": columns},
        ]
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    definition = _definition(result, "er")
    assert [(t["x"], t["y"], t["w"]) for t in definition["tables"]] == [
        (24, 24, 240),
        (360, 24, 240),
        (696, 24, 240),
        (24, 172, 240),
    ]
    assert definition["width"] == 960


def test_render_diagram_when_unknown() -> None:
    """知らない種類（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="gantt"):
        render_diagram({}, "gantt", HEAD)  # type: ignore[arg-type]


def test_er_table_titles() -> None:
    """物理名と論理名（正常系）。"""
    # 準備
    tables = [
        {"name": "customers", "title": "顧客"},
        {"name": "payments", "title": "支払い"},
    ]
    # 実行
    result = er_table_titles(tables)
    # 検証
    assert result == {"customers": "顧客", "顧客": "顧客", "payments": "支払い", "支払い": "支払い"}


def test_er_table_titles_when_duplicated_or_untitled() -> None:
    """重なるキーと論理名の無いテーブル（正常系）。"""
    # 準備
    tables = [{"name": "a", "title": "A"}, {"name": "A", "title": "B"}, {"name": "c"}]
    # 実行
    result = er_table_titles(tables)
    # 検証
    assert result["A"] == "A"
    assert "c" not in result


def test_render_mermaid() -> None:
    """シーケンス図（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  participant A as 画面\n  A->>B: 読む"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    definition = _definition(result, "sequence")
    assert [p["name"] for p in definition["participants"]] == ["画面", "B"]
    assert [step["label"] for step in definition["steps"]] == ["読む"]


def test_render_mermaid_when_flowchart() -> None:
    """フローチャート（正常系）。"""
    # 実行
    result = render_mermaid("flowchart TD\n  a --> b", HEAD)
    # 検証
    assert len(_definition(result, "flow")["nodes"]) == 2


def test_render_mermaid_when_unreadable() -> None:
    """読み取れないコード（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  A->>B: 読む\n  Note over A: 補足"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    assert result == f"```mermaid\n{code}\n```"
