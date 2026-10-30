export type TocItem = { id: string; text: string; level: 2 | 3 };

/** mdmark が描いた本文の要素から見出し 2・3 を並べる */
export const readToc = (root: HTMLElement): TocItem[] =>
  Array.from(root.querySelectorAll("h2[id], h3[id]")).map((heading) => ({
    id: heading.id,
    text: heading.textContent ?? "",
    level: heading.tagName === "H2" ? 2 : 3,
  }));

const HEADING = /^(#{2,3}) +(.+?)\s*$/;
const FENCE = /^(```|~~~)/;

/** Markdown をコードブロックの外の `## `・`### ` の行で区切り、見出しの文字列 → 中身にする */
const sections = (markdown: string): Map<string, string> => {
  const result = new Map<string, string>();
  const seen = new Map<string, number>();
  let current: string | null = null;
  let body: string[] = [];
  let fenced = false;
  const flush = () => {
    if (current !== null) result.set(current, body.map((line) => line.trimEnd()).join("\n").trimEnd());
  };
  for (const line of markdown.split("\n")) {
    if (FENCE.test(line)) fenced = !fenced;
    const match = fenced ? null : HEADING.exec(line);
    if (match) {
      flush();
      const text = match[2];
      const count = (seen.get(text) ?? 0) + 1;
      seen.set(text, count);
      current = count === 1 ? text : `${text}#${count}`;
      body = [];
    } else {
      body.push(line);
    }
  }
  flush();
  return result;
};

/** 2 つの Markdown を見出し 2・3 で区切り、中身が違う・比較元に無い見出しの文字列を返す */
export const changedSections = (markdown: string, baseMarkdown: string | null): Set<string> => {
  const current = sections(markdown);
  const base = baseMarkdown === null ? null : sections(baseMarkdown);
  const changed = new Set<string>();
  for (const [heading, body] of current) {
    if (base === null || base.get(heading) !== body) changed.add(heading.replace(/#\d+$/, ""));
  }
  return changed;
};
