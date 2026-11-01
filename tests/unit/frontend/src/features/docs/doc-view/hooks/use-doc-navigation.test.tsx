import { act, screen, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";

import { compareBase, useDocNavigation } from "@/features/docs/doc-view/hooks/use-doc-navigation";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import type { DocComment } from "@/features/docs/shared/comments/comment-store";
import { refsResponse } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

type Navigation = ReturnType<typeof useDocNavigation>;

/** フックの返す操作を外へ渡すだけの部品 */
const Probe = ({ search, onReady }: { search: DocViewSearch; onReady: (navigation: Navigation) => void }) => {
  onReady(useDocNavigation("s", "a.md", search, refsResponse() as never));
  return <p>probe</p>;
};

const renderNavigation = async (path: string, search: DocViewSearch) => {
  const holder: { current?: Navigation } = {};
  const { router } = renderInRouter(
    <Probe search={search} onReady={(navigation) => (holder.current = navigation)} />,
    path,
  );
  await screen.findByText("probe");
  return { router, navigation: holder as Required<typeof holder> };
};

test("test_compare_base", () => {
  expect(compareBase(refsResponse() as never, undefined)).toBe("7c0aa11");
});

test("test_compare_base_when_other_rev", () => {
  expect(compareBase(refsResponse() as never, "v1")).toBe("main");
});

test("test_compare_base_when_no_commits", () => {
  const refs = refsResponse({ commits: [{ commit: "8b1d4e0", date: "2026-10-26T11:30:00+09:00", subject: "x" }] });

  expect(compareBase(refs as never, undefined)).toBeUndefined();
  expect(compareBase(undefined, undefined)).toBeUndefined();
});

test("test_use_doc_navigation", async () => {
  const { router, navigation } = await renderNavigation("/s/a.md?rev=v1&base=v0", { rev: "v1", base: "v0" });

  act(() => navigation.current.openDoc("b.md"));

  await waitFor(() => expect(router.state.location.pathname).toBe("/s/b.md"));
  expect(router.state.location.search).toEqual({ rev: "v1" });
});

test("test_use_doc_navigation_when_select_ref", async () => {
  const { router, navigation } = await renderNavigation("/s/a.md?base=v0", { base: "v0" });

  act(() => navigation.current.selectRef("v2"));

  await waitFor(() => expect(router.state.location.search).toEqual({ rev: "v2", base: "v0" }));
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_use_doc_navigation_when_start_compare", async () => {
  const { router, navigation } = await renderNavigation("/s/a.md", {});

  act(() => navigation.current.startCompare());

  await waitFor(() => expect(router.state.location.search).toEqual({ base: "7c0aa11" }));
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_use_doc_navigation_when_clear_diff", async () => {
  const { router, navigation } = await renderNavigation("/s/a.md?rev=v1&base=v0", { rev: "v1", base: "v0" });

  act(() => navigation.current.clearDiff());

  await waitFor(() => expect(router.state.location.search).toEqual({ rev: "v1" }));
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_use_doc_navigation_when_locate", async () => {
  const { router, navigation } = await renderNavigation("/s/a.md", {});

  act(() => navigation.current.locate({ source: "t", path: "c.md", ref: "v3" } as DocComment));

  await waitFor(() => expect(router.state.location.pathname).toBe("/t/c.md"));
  expect(router.state.location.search).toEqual({ rev: "v3" });
});
