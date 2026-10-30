import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { DocTabs } from "@/features/docs/doc-view/components/doc-tabs";
import { page } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

test("test_doc_tabs", async () => {
  const tabs = [
    { title: "設計書", active: true, items: [page("A", "a.md")] },
    { title: "規約", active: false, items: [page("B", "b.md")] },
  ];

  renderInRouter(
    <DocTabs tabs={tabs as never} currentIndex={0} source="s" search={{}} onEmptyTab={vi.fn()} />,
  );

  const link = await screen.findByRole("link", { name: "規約" });
  expect(link.getAttribute("href")).toBe("/s/b.md");
});

test("test_doc_tabs_when_empty", async () => {
  const onEmptyTab = vi.fn();
  const empty = { title: "空", active: false, items: [] };
  const tabs = [{ title: "設計書", active: true, items: [page("A", "a.md")] }, empty];

  renderInRouter(
    <DocTabs tabs={tabs as never} currentIndex={0} source="s" search={{}} onEmptyTab={onEmptyTab} />,
  );
  await userEvent.click(await screen.findByText("空"));

  expect(onEmptyTab).toHaveBeenCalledTimes(1);
  expect(onEmptyTab).toHaveBeenCalledWith(empty);
});
