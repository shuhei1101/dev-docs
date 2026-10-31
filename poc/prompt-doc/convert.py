"""PoC: プロンプトの YAML（標準入力）から mdmark の Markdown（標準出力）を出す。"""

from __future__ import annotations

import html
import re
import sys

import jinja2
import yaml

HOOK_CHAR_LIMIT = 1000
ROLES = ("system", "user", "assistant")
EXPR_PATTERN = re.compile(r"\{\{\s*(.*?)\s*\}\}")
FOR_PATTERN = re.compile(r"\{%-?\s*for\s+(\w+)\s+in\s+(\w+)")
TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def flatten_vars(vars_: dict, prefix: str = "") -> list[tuple[str, dict]]:
    """変数の定義を深さ優先で辿り、パスと定義の組にする。"""
    rows = []
    for name, spec in vars_.items():
        path = f"{prefix}{name}"
        rows.append((path, spec))
        items = spec.get("items")
        # 配列は要素のキーを `[]` 付きのパスで辿る
        if spec.get("type") == "array" and isinstance(items, dict) and items.get("properties"):
            rows += flatten_vars(items["properties"], f"{path}[].")
        # オブジェクトはキーを `.` 付きのパスで辿る
        elif spec.get("properties"):
            rows += flatten_vars(spec["properties"], f"{path}.")
    return rows


def flow(value: object) -> str:
    """値を YAML のフロー形式の 1 行にする。"""
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, sort_keys=False, width=10**6)
    # スカラーの末尾に付く文書の終わりの印を外す
    return dumped.removesuffix("...\n").strip()


def cell(text: object) -> str:
    """表のセルに入れる文字列にする。"""
    return str(text).replace("|", "\\|").replace("\n", " ")


def var_table(vars_: dict) -> list[str]:
    """変数の表を出す。"""
    lines = ["| 変数 | 型 | 必須 | 例 | 説明 | 出どころ |", "| --- | --- | --- | --- | --- | --- |"]
    for path, spec in flatten_vars(vars_):
        example = f"`{cell(flow(spec['example']))}`" if "example" in spec else "-"
        required = "✅" if spec.get("required") else "-"
        lines.append(
            f"| `{path}` | {spec.get('type', '-')} | {required} | {example} | "
            f"{cell(spec.get('description', ''))} | {cell(spec.get('source', '-'))} |"
        )
    return lines


def hint_for(expr: str, paths: dict[str, dict], aliases: dict[str, str]) -> str | None:
    """`{{ 式 }}` の変数のパスから、説明・型・例のヒントの文を作る。"""
    head = re.split(r"[\s|(]", expr, maxsplit=1)[0]
    parts = head.split(".")
    # ループの変数は、元の配列の要素のパスに読み替える
    if parts[0] in aliases:
        head = ".".join([f"{aliases[parts[0]]}[]", *parts[1:]])
    spec = paths.get(head)
    if spec is None:
        return None
    example = flow(spec["example"]) if "example" in spec else "-"
    return f"{spec.get('description', '')}（型: {spec.get('type', '-')}、例: {example}）"


def template_html(text: str, paths: dict[str, dict]) -> str:
    """部品の本文を、変数にヒントを付けた <pre> の HTML にする。"""
    aliases = {m.group(1): m.group(2) for m in FOR_PATTERN.finditer(text)}
    out = []
    last = 0
    for m in EXPR_PATTERN.finditer(text):
        out.append(html.escape(text[last : m.start()]))
        hint = hint_for(m.group(1), paths, aliases)
        token = html.escape(m.group(0))
        out.append(f'<span data-hint="{html.escape(hint)}">{token}</span>' if hint else token)
        last = m.end()
    out.append(html.escape(text[last:]))
    return "<pre><code>" + "".join(out) + "</code></pre>"


def languages(doc: dict) -> list[str]:
    """部品の本文に出る言語を、注入する言語を先頭にして並べる。"""
    langs = [doc["lang"]]
    for part in doc["parts"]:
        for t in part["texts"]:
            if t["lang"] not in langs:
                langs.append(t["lang"])
    return langs


def check_types(values: dict, vars_: dict) -> list[str]:
    """値が変数の `type` に合うかを確かめ、合わない変数の理由を返す。"""
    errors = []
    for name, spec in vars_.items():
        check = TYPE_CHECKS.get(spec.get("type"))
        if name in values and check and not check(values[name]):
            errors.append(f"`{name}` は {spec['type']} ですが、`{flow(values[name])}` が入っています")
    return errors


def render_set(doc: dict, values: dict, lang: str, env: jinja2.Environment) -> list[str]:
    """1 つの組を 1 つの言語で描画した結果の Markdown を返す。"""
    errors = check_types(values, doc.get("vars", {}))
    if errors:
        return ["> [!CAUTION]", "> この組は描画できません。", *[f"> - {e}" for e in errors]]
    used: list[tuple[dict, str]] = []
    unused: list[str] = []
    try:
        for part in doc["parts"]:
            # when が偽の部品は使わない
            if "when" in part and env.from_string(part["when"]).render(values).strip() in ("False", "", "[]"):
                unused.append(part["id"])
                continue
            text = next((t["text"] for t in part["texts"] if t["lang"] == lang), None)
            # この言語の本文が無い部品は描画しない
            if text is None:
                unused.append(f"{part['id']}（{lang} の本文なし）")
                continue
            used.append((part, env.from_string(text).render(values)))
    except jinja2.UndefinedError as e:
        return ["> [!CAUTION]", f"> この組は描画できません。未定義の変数: {e.message}"]
    total = sum(len(r) for _, r in used)
    lines: list[str] = []
    if doc["kind"] == "hook" and total > HOOK_CHAR_LIMIT:
        lines += ["> [!WARNING]", f"> 描画した結果が {total:,} 字で、{HOOK_CHAR_LIMIT:,} 字を超えています。", ""]
    # kind: llm は role ごとのメッセージに分ける
    if doc["kind"] == "llm":
        for role in ROLES:
            body = "\n\n".join(r for p, r in used if p.get("role") == role)
            if body:
                lines += [f"**{role}**", "", "```text", body.rstrip("\n"), "```", ""]
    else:
        lines += ["```text", "".join(r for _, r in used).rstrip("\n"), "```", ""]
    lines.append(f"字数: {total:,} 字 / 使わなかった部品: {', '.join(unused) if unused else 'なし'}")
    return lines


def lang_tabs(doc: dict, body_of) -> list[str]:
    """言語のタブを出す。`body_of(lang)` が各タブの中身を返す。"""
    lines = ["<!-- tabs: group=lang -->", ""]
    for lang in languages(doc):
        name = f"{lang}（注入）" if lang == doc["lang"] else lang
        lines += [f"#### {name}", "", *body_of(lang), ""]
    return lines + ["<!-- /tabs -->", ""]


def part_body(part: dict, lang: str, paths: dict[str, dict]) -> list[str]:
    """テンプレートの部品の 1 言語分の中身を返す。"""
    text = next((t["text"] for t in part["texts"] if t["lang"] == lang), None)
    if text is None:
        return [f"{lang} の本文はありません。"]
    return ["<!-- html -->", "", "```html", template_html(text, paths), "```", "", "<!-- /html -->"]


def convert(doc: dict) -> str:
    """プロンプトの YAML を Markdown にする。"""
    vars_ = doc.get("vars", {})
    paths = dict(flatten_vars(vars_))
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    lines = [f"# {doc['name']}", "", f"`badge:kind: {doc['kind']}` `badge:lang: {doc['lang']}`", "", doc["description"], ""]
    lines += ["## 変数", "", *var_table(vars_), ""]

    # テンプレート: 部品ごとのセクションに言語のタブを置く
    lines += ["## テンプレート", ""]
    for part in doc["parts"]:
        meta = [f"role: `{part['role']}`"] if part.get("role") else []
        meta += [f"when: `{part['when']}`"] if part.get("when") else []
        lines += [f"### {part['id']}", "", *([" / ".join(meta), ""] if meta else [])]
        lines += lang_tabs(doc, lambda lang, part=part: part_body(part, lang, paths))

    # 例: 組ごとのセクション（2 つ目以降は閉じる）に言語のタブを置く
    lines += ["## 例", ""]
    defaults = {name: spec["example"] for name, spec in vars_.items() if "example" in spec}
    sets = [("既定の例", defaults)] + [(ex["name"], {**defaults, **ex["values"]}) for ex in doc.get("examples", [])]
    for i, (name, values) in enumerate(sets):
        lines += [f"### {name}", "", *(["<!-- section: closed -->", ""] if i > 0 else [])]
        lines += lang_tabs(doc, lambda lang, values=values: render_set(doc, values, lang, env))
    return "\n".join(lines)


def main() -> None:
    """標準入力の YAML を変換して標準出力へ書く。"""
    sys.stdout.write(convert(yaml.safe_load(sys.stdin.read())))


if __name__ == "__main__":
    main()
