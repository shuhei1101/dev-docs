import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";

import { MetadataTable } from "@/features/metadata/metadata/metadata-table";
import { usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import { metadataResponse } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const kindOf = (id: string) => {
  const kind = metadataResponse().kinds.find((item) => item.id === id);
  if (kind === undefined) throw new Error(id);
  return kind as never;
};

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {} });
});

test("test_metadata_table_when_edited", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" />);

  await userEvent.click(await screen.findByRole("button", { name: "タグ topic:a を編集" }));
  const input = screen.getByRole("textbox");
  await userEvent.clear(input);
  await userEvent.type(input, "topic:a, topic:b{Enter}");

  const edits = usePendingEditsStore.getState().bySource.sample ?? [];
  expect(edits).toHaveLength(1);
  expect(edits[0]).toMatchObject({ op: "update", docId: "n1", values: { tags: ["topic:a", "topic:b"] } });
});

test("test_metadata_table_when_readonly", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" />);

  expect((await screen.findAllByText("notes/n1.yaml")).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "文書 notes/n1.yaml を編集" })).toBeNull();
});

test("test_metadata_table_when_add_duplicate", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));
  await userEvent.type(screen.getByRole("textbox", { name: "ID" }), "source");
  await userEvent.click(screen.getByRole("button", { name: "追加" }));

  expect(screen.getByText("この ID は使用されています。別の ID を入力してください")).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});

test("test_metadata_table_when_edited_label", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" />);

  await userEvent.click(await screen.findByRole("button", { name: "タグ topic:a を編集" }));
  await userEvent.type(screen.getByRole("textbox"), ", topic:b{Enter}");

  const edits = usePendingEditsStore.getState().bySource.sample ?? [];
  expect(edits[0]?.label).toBe("タグ: notes/n1.yaml");
});

test("test_metadata_table_when_add_focus", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));

  expect(screen.getByRole("textbox", { name: "ID" })).toHaveFocus();
});

test("test_metadata_table_when_add_cancel", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));
  await userEvent.type(screen.getByRole("textbox", { name: "ID" }), "kind{Escape}");

  expect(screen.queryByRole("textbox", { name: "ID" })).toBeNull();
  expect(screen.getByRole("button", { name: "行追加" })).toHaveFocus();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});
