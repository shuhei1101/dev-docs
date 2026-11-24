import { screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DocSidebar } from "@/features/docs/doc-view/components/doc-sidebar";
import { group, page } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

test("test_doc_sidebar", async () => {
  const tab = {
    title: "設計書",
    active: true,
    items: [group("設計", [page("A", "a.md"), page("B", "b.md")])],
  };

  renderInRouter(
    <DocSidebar tab={tab as never} source="s" currentPath="a.md" search={{}} />,
  );

  expect(await screen.findByText("設計")).toBeInTheDocument();
  const links = await screen.findAllByRole("link");
  expect(links).toHaveLength(2);
  expect(screen.getByRole("link", { name: "A" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByRole("link", { name: "B" })).not.toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("test_doc_sidebar_when_deleted", async () => {
  const tab = {
    title: "設計書",
    active: true,
    items: [group("設計", [page("C", "c.md", "deleted")])],
  };

  renderInRouter(
    <DocSidebar
      tab={tab as never}
      source="s"
      currentPath="a.md"
      search={{ rev: "main", base: "v1" }}
    />,
  );

  const link = await screen.findByRole("link", { name: /C/ });
  expect(link.getAttribute("href")).toBe("/s/c.md?rev=v1");
  expect(screen.getByLabelText("削除")).toBeInTheDocument();
});

test("test_doc_sidebar_when_excluded", async () => {
  const excludedPage = { ...page("B", "b.md"), excluded: true };
  const tab = {
    title: "設計書",
    active: true,
    items: [group("設計", [page("A", "a.md"), excludedPage])],
  };

  renderInRouter(
    <DocSidebar tab={tab as never} source="s" currentPath="a.md" search={{}} />,
  );

  const link = await screen.findByRole("link", { name: /B/ });
  expect(link.getAttribute("href")).toBe("/s/b.md");
  expect(screen.getAllByRole("img", { name: "検索から除外" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "A" })).not.toContainElement(
    screen.getByRole("img", { name: "検索から除外" }),
  );
});
