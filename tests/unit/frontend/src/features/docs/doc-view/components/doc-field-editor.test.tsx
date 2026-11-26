import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import {
  DocFieldEditor,
  EditableTitle,
} from "@/features/docs/doc-view/components/doc-field-editor";
import type { DocumentEdit, EditBlock } from "@/shared/api/generated/model";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit, editBlock } from "@tests/helpers/fixtures";

const mount = vi.hoisted(() => vi.fn());

vi.mock(
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@develop/dist/index.js",
  () => ({ mount }),
);

/** mdmark が最後に描いた Markdown（最初の `mount` と、その後の `update` の最後） */
const rendered: string[] = [];
const lastMarkdown = () => rendered.at(-1) ?? "";

beforeEach(() => {
  mount.mockReset();
  rendered.length = 0;
  mount.mockImplementation((_element: unknown, options: { markdown: string }) => {
    rendered.push(options.markdown);
    return { update: vi.fn((markdown: string) => rendered.push(markdown)), destroy: vi.fn() };
  });
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

const edit = docEdit() as unknown as DocumentEdit;

const renderEditor = (target: DocumentEdit = edit, onMarkdownOpen = vi.fn()) =>
  render(
    <DocFieldEditor
      source="s"
      docId="s@main:notes/n1"
      edit={target}
      onMarkdownOpen={onMarkdownOpen}
    />,
  );

const pendingValues = () =>
  (usePendingEditsStore.getState().bySource.s ?? []).map((item) => item.values);

test("test_doc_field_editor", async () => {
  renderEditor();

  await userEvent.click(screen.getByRole("button", { name: "概要 を編集" }));
  const input = screen.getByRole("textbox", { name: "概要" });
  await userEvent.clear(input);
  await userEvent.type(input, "修正後の概要{Enter}");

  expect(
    screen.queryByRole("textbox", { name: "概要" }),
  ).not.toBeInTheDocument();
  expect(pendingValues()).toEqual([{ summary: "修正後の概要" }]);
  await waitFor(() => expect(lastMarkdown()).toContain("修正後の概要"));
  expect(screen.getByText("変更あり")).toBeInTheDocument();
});

test("test_doc_field_editor_when_enum", async () => {
  renderEditor();

  await userEvent.click(screen.getByRole("button", { name: "状態 を編集" }));
  await userEvent.click(screen.getByRole("combobox", { name: "状態" }));
  await userEvent.click(await screen.findByRole("option", { name: "current" }));

  expect(pendingValues()).toEqual([{ status: "current" }]);
});

test("test_doc_field_editor_when_table", async () => {
  renderEditor();

  await userEvent.click(
    screen.getByRole("button", { name: "置き換え を編集" }),
  );
  const cell = screen.getByRole("textbox", {
    name: "置き換え の 2 行目の replacement",
  });
  await userEvent.clear(cell);
  await userEvent.type(cell, "e");

  expect(pendingValues()).toEqual([
    {
      rows: [
        { word: "a", replacement: "b" },
        { word: "c", replacement: "e" },
      ],
    },
  ]);
  expect(
    screen.queryByRole("button", { name: /行を追加|行を削除/ }),
  ).not.toBeInTheDocument();
});

test("test_doc_field_editor_when_composing", async () => {
  renderEditor();
  await userEvent.click(screen.getByRole("button", { name: "概要 を編集" }));
  const input = screen.getByRole("textbox", { name: "概要" });

  input.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      isComposing: true,
    }),
  );

  expect(screen.getByRole("textbox", { name: "概要" })).toBeInTheDocument();
});

test("test_doc_field_editor_when_markdown", async () => {
  const onMarkdownOpen = vi.fn();
  renderEditor(edit, onMarkdownOpen);

  await userEvent.click(
    screen.getByRole("button", { name: "i1 の 本文 を編集" }),
  );

  expect(onMarkdownOpen).toHaveBeenCalledWith(
    expect.objectContaining({ path: "#items[i1].body" }),
  );
  expect(
    screen.queryByRole("textbox", { name: "i1 の 本文" }),
  ).not.toBeInTheDocument();
});

test("test_doc_field_editor_when_value_not_in_markdown", async () => {
  const linked = docEdit({
    blocks: [
      editBlock("#items[i1].body", {
        label: "i1 の 本文",
        type: "markdown",
        markdown: "[B](../b.yaml) を参照する",
        value: "[B](id:b) を参照する",
      }),
    ],
  }) as unknown as DocumentEdit;
  usePendingEditsStore.getState().upsert(
    "s",
    {
      key: "body:n1:#items[i1].body",
      kind: "body",
      op: "update",
      docId: "n1",
      docKind: "note",
      expectedVersion: "v-n1",
      docPath: "notes/n1.yaml",
      values: { "#items[i1].body": "修正後の本文" },
      before: { "#items[i1].body": "[B](id:b) を参照する" },
      label: "i1 の 本文（notes/n1.yaml）",
    },
    "ccc3333",
  );

  renderEditor(linked);

  await waitFor(() => expect(lastMarkdown()).toBe("修正後の本文"));
  expect(screen.getByText("変更あり")).toBeInTheDocument();
});

test("test_doc_field_editor_when_value_repeated", async () => {
  const repeated = docEdit({
    blocks: [
      editBlock("summary", {
        label: "概要",
        markdown: "**概要**: 概要",
        value: "概要",
      }),
    ],
  }) as unknown as DocumentEdit;
  renderEditor(repeated);

  await userEvent.click(screen.getByRole("button", { name: "概要 を編集" }));
  const input = screen.getByRole("textbox", { name: "概要" });
  await userEvent.clear(input);
  await userEvent.type(input, "修正後{Escape}");

  await waitFor(() => expect(lastMarkdown()).toBe("修正後"));
});

test("test_doc_field_editor_when_value_has_dollar", async () => {
  renderEditor();

  await userEvent.click(screen.getByRole("button", { name: "概要 を編集" }));
  const input = screen.getByRole("textbox", { name: "概要" });
  await userEvent.clear(input);
  await userEvent.type(input, "$& と $$ と $'{Enter}");

  await waitFor(() => expect(lastMarkdown()).toContain("$& と $$ と $'"));
});

test("test_editable_title", async () => {
  render(
    <EditableTitle
      source="s"
      edit={edit}
      block={edit.titleBlock as EditBlock}
    />,
  );

  await userEvent.click(
    screen.getByRole("button", { name: "タイトル を編集" }),
  );
  const input = screen.getByRole("textbox", { name: "タイトル" });
  await userEvent.clear(input);
  await userEvent.type(input, "新規のタイトル{Escape}");

  expect(
    screen.getByRole("heading", { level: 1, name: "新規のタイトル" }),
  ).toBeInTheDocument();
  expect(pendingValues()).toEqual([{ title: "新規のタイトル" }]);
});
