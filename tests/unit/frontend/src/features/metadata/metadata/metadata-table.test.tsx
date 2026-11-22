import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";

import { MetadataTable } from "@/features/metadata/metadata/metadata-table";
import { usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import { metadataResponse } from "@tests/helpers/fixtures";

const kindOf = (id: string) => {
  const kind = metadataResponse().kinds.find((item) => item.id === id);
  if (kind === undefined) throw new Error(id);
  return kind as never;
};

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {} });
});

test("test_metadata_table_when_edited", async () => {
  render(<MetadataTable source="sample" kind={kindOf("tags")} query="" />);

  await userEvent.click(screen.getByRole("button", { name: "タグ topic:a を編集" }));
  const input = screen.getByRole("textbox");
  await userEvent.clear(input);
  await userEvent.type(input, "topic:a, topic:b{Enter}");

  const edits = usePendingEditsStore.getState().bySource.sample ?? [];
  expect(edits).toHaveLength(1);
  expect(edits[0]).toMatchObject({ op: "update", docId: "n1", values: { tags: ["topic:a", "topic:b"] } });
});

test("test_metadata_table_when_readonly", () => {
  render(<MetadataTable source="sample" kind={kindOf("tags")} query="" />);

  expect(screen.queryByRole("button", { name: "文書 notes/n1.yaml を編集" })).toBeNull();
  expect(screen.getAllByText("notes/n1.yaml").length).toBeGreaterThan(0);
});

test("test_metadata_table_when_add_duplicate", async () => {
  render(<MetadataTable source="sample" kind={kindOf("terms")} query="" />);

  await userEvent.click(screen.getByRole("button", { name: "行追加" }));
  await userEvent.type(screen.getByRole("textbox", { name: "ID" }), "source");
  await userEvent.click(screen.getByRole("button", { name: "追加" }));

  expect(screen.getByText("この ID は使用されています。別の ID を入力してください")).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});
