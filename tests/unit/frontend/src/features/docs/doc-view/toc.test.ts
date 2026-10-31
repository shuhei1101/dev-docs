import { expect, test } from "vitest";

import { changedSections, readToc } from "@/features/docs/doc-view/toc";

test("test_read_toc", () => {
  const root = document.createElement("div");
  root.innerHTML = '<h2 id="a">A</h2><h3 id="b">B</h3><h4 id="c">C</h4>';

  expect(readToc(root)).toEqual([
    { id: "a", text: "A", level: 2 },
    { id: "b", text: "B", level: 3 },
  ]);
});

test("test_changed_sections", () => {
  const base = "## A\nold\n## B\nsame\n";
  const markdown = "## A\nnew\n## B\nsame\n";

  expect(changedSections(markdown, base)).toEqual(new Set(["A"]));
});

test("test_changed_sections_when_added_heading", () => {
  const base = "## A\nx\n";
  const markdown = "## A\nx\n### C\nnew\n";

  expect(changedSections(markdown, base).has("C")).toBe(true);
});

test("test_changed_sections_when_code_block", () => {
  const base = "## A\nold\n";
  const markdown = "## A\n```\n## x\n```\n";

  expect(changedSections(markdown, base).has("x")).toBe(false);
});

test("test_changed_sections_when_base_missing", () => {
  const markdown = "## A\na\n### B\nb\n";

  expect(changedSections(markdown, null)).toEqual(new Set(["A", "B"]));
});
