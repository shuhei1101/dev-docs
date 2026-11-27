import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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

const twoGroups = (bPages: ReturnType<typeof page>[]) => ({
  title: "設計書",
  active: true,
  items: [group("A", [page("A1", "a.md"), page("A2", "a2.md")]), group("B", bPages)],
});

/** `移動` を押すと currentPath を `to` に変えて描き直す */
const Moving = ({ tab, from, to }: { tab: unknown; from: string; to: string }) => {
  const [path, setPath] = useState(from);
  return (
    <>
      <button type="button" onClick={() => setPath(to)}>
        移動
      </button>
      <DocSidebar tab={tab as never} source="s" currentPath={path} search={{}} />
    </>
  );
};

test("test_doc_sidebar_when_group_toggled", async () => {
  renderInRouter(
    <DocSidebar tab={twoGroups([page("B1", "b.md")]) as never} source="s" currentPath="a.md" search={{}} />,
  );

  expect(await screen.findByRole("button", { name: "A" })).toHaveAttribute("aria-expanded", "true");
  const b = screen.getByRole("button", { name: "B" });
  expect(b).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "B1" })).not.toBeInTheDocument();

  await userEvent.click(b);

  expect(b).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "B1" })).toBeInTheDocument();
});

test("test_doc_sidebar_when_current_changed", async () => {
  renderInRouter(<Moving tab={twoGroups([page("C", "c.md")])} from="a.md" to="c.md" />);
  const b = await screen.findByRole("button", { name: "B" });
  expect(b).toHaveAttribute("aria-expanded", "false");

  await userEvent.click(screen.getByRole("button", { name: "移動" }));

  expect(b).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "C" })).toHaveAttribute("aria-current", "page");
});

test("test_doc_sidebar_when_changed_in_group", async () => {
  renderInRouter(
    <DocSidebar tab={twoGroups([page("C", "c.md", "modified")]) as never} source="s" currentPath="a.md" search={{}} />,
  );

  expect(await screen.findByRole("button", { name: "B" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByLabelText("変更")).toBeInTheDocument();
});

test("test_doc_sidebar_when_nested", async () => {
  const nested = (titles: string[]): unknown =>
    titles.length === 0
      ? page("Deep", "deep.md")
      : { ...group(titles[0], []), items: [nested(titles.slice(1))] };
  const tab = { title: "設計書", active: true, items: [nested(["L1", "L2", "L3", "L4"])] };

  renderInRouter(<DocSidebar tab={tab as never} source="s" currentPath="deep.md" search={{}} />);

  for (const title of ["L1", "L2", "L3", "L4"]) {
    expect(await screen.findByRole("button", { name: title })).toHaveAttribute("aria-expanded", "true");
  }
  expect(screen.getByRole("link", { name: "Deep" })).toHaveAttribute("aria-current", "page");
});

test("test_doc_sidebar_when_moved_keeps_closed", async () => {
  renderInRouter(<Moving tab={twoGroups([page("C", "c.md", "modified")])} from="a.md" to="a2.md" />);
  const b = await screen.findByRole("button", { name: "B" });
  await userEvent.click(b);
  expect(b).toHaveAttribute("aria-expanded", "false");

  await userEvent.click(screen.getByRole("button", { name: "移動" }));

  expect(b).toHaveAttribute("aria-expanded", "false");
});

/** `差分を表示` を押すと `B` の中の page の change を modified に変えて描き直す */
const ChangeAppearing = () => {
  const [change, setChange] = useState<string | null>(null);
  return (
    <>
      <button type="button" onClick={() => setChange("modified")}>
        差分を表示
      </button>
      <DocSidebar tab={twoGroups([page("C", "c.md", change)]) as never} source="s" currentPath="a.md" search={{}} />
    </>
  );
};

test("test_doc_sidebar_when_change_appeared", async () => {
  renderInRouter(<ChangeAppearing />);
  const b = await screen.findByRole("button", { name: "B" });
  expect(b).toHaveAttribute("aria-expanded", "false");

  await userEvent.click(screen.getByRole("button", { name: "差分を表示" }));

  expect(b).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByLabelText("変更")).toBeInTheDocument();
});

test("test_doc_sidebar_when_long_name", async () => {
  const longGroup = "設計".repeat(50);
  const longPage = "文書".repeat(50);
  const tab = {
    title: "設計書",
    active: true,
    items: [group(longGroup, [page(longPage, "a.md")])],
  };

  renderInRouter(
    <DocSidebar tab={tab as never} source="s" currentPath="a.md" search={{}} />,
  );

  const groupName = await screen.findByText(longGroup);
  const pageName = screen.getByText(longPage);
  expect(groupName).toHaveClass("truncate");
  expect(groupName).toHaveAttribute("title", longGroup);
  expect(pageName).toHaveClass("truncate");
  expect(pageName).toHaveAttribute("title", longPage);
});
