import { screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { MissingLinks } from "@/features/docs/not-found/components/missing-links";
import type { MissingDescription } from "@/features/docs/not-found/missing";
import { renderInRouter } from "@tests/helpers/render";

const SERVING = [
  { id: "s", writable: true },
  { id: "t", writable: false },
];

const missing = (kind: MissingDescription["kind"]) => ({ kind }) as MissingDescription;

test("test_missing_links", async () => {
  renderInRouter(<MissingLinks missing={missing("doc")} source="s" rev="v1" serving={SERVING} />);

  expect(await screen.findByRole("link", { name: "s のトップを開く" })).toHaveAttribute("href", "/s?rev=v1");
  expect(screen.getByRole("link", { name: "設定を開く" })).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "配信中の配信元" })).toBeNull();
});

test("test_missing_links_when_source_missing", async () => {
  renderInRouter(<MissingLinks missing={missing("source")} serving={SERVING} />, "/unknown/a.md");

  expect(await screen.findByRole("link", { name: "設定を開く" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /のトップを開く$/ })).toBeNull();
  const list = screen.getByRole("list", { name: "配信中の配信元" });
  expect(list.querySelectorAll("a")).toHaveLength(2);
});

test("test_missing_links_when_no_serving", async () => {
  renderInRouter(<MissingLinks missing={missing("not_served")} serving={[]} />, "/broken/a.md");

  expect(await screen.findByRole("link", { name: "設定を開く" })).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "配信中の配信元" })).toBeNull();
});
