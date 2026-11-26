import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { MetadataTable } from "@/features/metadata/metadata/metadata-table";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { metadataResponse, metadataRow } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const kindOf = (id: string) => {
  const kind = metadataResponse().kinds.find((item) => item.id === id);
  if (kind === undefined) throw new Error(id);
  return kind as never;
};

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

test("test_metadata_table_when_edited", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" baseCommit="aaa1111" />);

  await userEvent.click(await screen.findByRole("button", { name: "タグ topic:a を編集" }));
  const input = screen.getByRole("textbox");
  await userEvent.clear(input);
  await userEvent.type(input, "topic:a, topic:b{Enter}");

  const edits = usePendingEditsStore.getState().bySource.sample ?? [];
  expect(edits).toHaveLength(1);
  expect(edits[0]).toMatchObject({
    op: "update",
    docId: "n1",
    docPath: "notes/n1.yaml",
    values: { tags: ["topic:a", "topic:b"] },
  });
  expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBe("aaa1111");
});

test("test_metadata_table_when_readonly", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" baseCommit="aaa1111" />);

  expect((await screen.findAllByText("notes/n1.yaml")).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "文書 notes/n1.yaml を編集" })).toBeNull();
});

test("test_metadata_table_when_add_duplicate", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" baseCommit="aaa1111" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));
  await userEvent.type(screen.getByRole("textbox", { name: "ID" }), "source");
  await userEvent.click(screen.getByRole("button", { name: "追加" }));

  expect(screen.getByText("この ID は使用されています。別の ID を入力してください")).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});

test("test_metadata_table_when_edited_label", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("tags")} query="" baseCommit="aaa1111" />);

  await userEvent.click(await screen.findByRole("button", { name: "タグ topic:a を編集" }));
  await userEvent.type(screen.getByRole("textbox"), ", topic:b{Enter}");

  const edits = usePendingEditsStore.getState().bySource.sample ?? [];
  expect(edits[0]?.label).toBe("タグ: notes/n1.yaml");
});

test("test_metadata_table_when_add_focus", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" baseCommit="aaa1111" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));

  expect(screen.getByRole("textbox", { name: "ID" })).toHaveFocus();
});

test("test_metadata_table_when_add_cancel", async () => {
  renderInRouter(<MetadataTable source="sample" kind={kindOf("terms")} query="" baseCommit="aaa1111" />);

  await userEvent.click(await screen.findByRole("button", { name: "行追加" }));
  await userEvent.type(screen.getByRole("textbox", { name: "ID" }), "kind{Escape}");

  expect(screen.queryByRole("textbox", { name: "ID" })).toBeNull();
  expect(screen.getByRole("button", { name: "行追加" })).toHaveFocus();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});

const tagsWithValue = (value: string) =>
  ({
    ...metadataResponse().kinds.find((item) => item.id === "tags"),
    rows: [metadataRow("n1", { path: "notes/n1.yaml", tags: [value] })],
  }) as never;

const textNodeOf = (element: HTMLElement, text: string): Text => {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.textContent === text) return node as Text;
  }
  throw new Error(text);
};

describe("押した位置", () => {
  afterEach(() => {
    delete (document as { caretPositionFromPoint?: unknown }).caretPositionFromPoint;
  });

  test("test_metadata_table_when_caret_at_clicked", async () => {
    renderInRouter(<MetadataTable source="sample" kind={tagsWithValue("project-index")} query="" baseCommit="aaa1111" />);
    const button = await screen.findByRole("button", { name: "タグ project-index を編集" });
    const offsetNode = textNodeOf(button, "project-index");
    Object.defineProperty(document, "caretPositionFromPoint", {
      value: vi.fn(() => ({ offsetNode, offset: 7 })),
      configurable: true,
    });

    await userEvent.click(button);

    const input = screen.getByRole<HTMLInputElement>("textbox");
    expect(input).toHaveFocus();
    expect([input.selectionStart, input.selectionEnd]).toEqual([7, 7]);
  });
});

test("test_metadata_table_when_caret_keyboard", async () => {
  renderInRouter(<MetadataTable source="sample" kind={tagsWithValue("project-index")} query="" baseCommit="aaa1111" />);
  (await screen.findByRole("button", { name: "タグ project-index を編集" })).focus();

  await userEvent.keyboard("{Enter}");

  expect(screen.getByRole<HTMLInputElement>("textbox").selectionStart).toBe("project-index".length);
});
