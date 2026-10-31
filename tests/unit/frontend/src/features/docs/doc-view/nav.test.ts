import { expect, test } from "vitest";

import { findActivePage, firstPagePath, pageTitle } from "@/features/docs/doc-view/nav";

const page = (title: string, path: string) => ({
  kind: "page" as const,
  title,
  path,
  items: [],
  change: null,
});
const group = (title: string, items: ReturnType<typeof page>[]) => ({
  kind: "group" as const,
  title,
  path: null,
  items,
  change: null,
});

test("test_find_active_page", () => {
  const tabs = [{ title: "設計書", active: true, items: [group("設計", [page("A", "a.md")])] }];

  const active = findActivePage(tabs, "a.md");

  expect(active.group).toBe("設計");
  expect(active.page?.path).toBe("a.md");
});

test("test_find_active_page_when_empty_tab", () => {
  const tabs = [{ title: "空", active: true, items: [] }];

  expect(findActivePage(tabs, "a.md").page).toBeNull();
});

test("test_first_page_path", () => {
  const tab = { title: "T", active: true, items: [group("G", [page("B", "b.md")]), page("C", "c.md")] };

  expect(firstPagePath(tab)).toBe("b.md");
});

test("test_first_page_path_when_empty", () => {
  expect(firstPagePath({ title: "T", active: true, items: [] })).toBeNull();
});

test("test_page_title", () => {
  const tab = { title: "設計書", active: true, items: [page("A", "a.md")] };

  const title = pageTitle({ tab, group: null, page: page("A", "a.md") }, "s");

  expect(title).toBe("A | s | dev-docs");
});
