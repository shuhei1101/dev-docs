import { screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { DocBreadcrumb } from "@/features/docs/doc-view/components/doc-breadcrumb";
import { group, page } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const designTab = { title: "設計", active: true, items: [group("設計", [page("A", "a.md")])] };
const emptyRuleTab = { title: "規約", active: false, items: [] };

const renderBreadcrumb = (emptyTab: unknown, groups: string[] = ["設計"]) =>
  renderInRouter(
    <DocBreadcrumb
      source="s"
      active={{ tab: designTab, groups, page: page("A", "a.md") } as never}
      emptyTab={emptyTab as never}
      search={{}}
    />,
  );

const crumbLabels = (nav: HTMLElement) =>
  within(nav)
    .getAllByRole("listitem")
    .map((item) => item.textContent);

test("test_doc_breadcrumb", async () => {
  renderBreadcrumb(null);

  const nav = await screen.findByRole("navigation", { name: "パンくず" });
  expect(crumbLabels(nav)).toEqual(["s", "設計", "設計", "A"]);
  expect(within(nav).getByRole("link", { name: "s" })).toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: "設計" })).toBeInTheDocument();
  expect(within(nav).getByText("A")).toHaveAttribute("aria-current", "page");
});

test("test_doc_breadcrumb_when_nested_group", async () => {
  renderBreadcrumb(null, ["設計書", "画面"]);

  const nav = await screen.findByRole("navigation", { name: "パンくず" });
  expect(crumbLabels(nav)).toEqual(["s", "設計", "設計書", "画面", "A"]);
  expect(within(nav).queryByRole("link", { name: "設計書" })).toBeNull();
  expect(within(nav).queryByRole("link", { name: "画面" })).toBeNull();
  expect(within(nav).getByText("A")).toHaveAttribute("aria-current", "page");
});

test("test_doc_breadcrumb_when_empty_tab", async () => {
  renderBreadcrumb(emptyRuleTab);

  const nav = await screen.findByRole("navigation", { name: "パンくず" });
  expect(crumbLabels(nav)).toEqual(["s", "規約"]);
  expect(within(nav).queryByRole("link", { name: "規約" })).toBeNull();
  expect(within(nav).getByText("規約")).toHaveAttribute("aria-current", "page");
  expect(within(nav).queryByText("設計")).toBeNull();
  expect(within(nav).queryByText("A")).toBeNull();
});
