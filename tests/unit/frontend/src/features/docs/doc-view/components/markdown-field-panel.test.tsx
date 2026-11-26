import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { MarkdownFieldPanel } from "@/features/docs/doc-view/components/markdown-field-panel";
import type { DocumentEdit, EditBlock } from "@/shared/api/generated/model";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit } from "@tests/helpers/fixtures";

const mount = vi.hoisted(() => vi.fn());

vi.mock(
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@develop/dist/index.js",
  () => ({ mount }),
);

const lastMarkdown = () =>
  (mount.mock.calls.at(-1)?.[1] as { markdown: string } | undefined)
    ?.markdown ?? "";

beforeEach(() => {
  mount.mockReset();
  mount.mockReturnValue({ update: vi.fn(), destroy: vi.fn() });
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

const edit = docEdit() as unknown as DocumentEdit;
const block = edit.blocks[2] as EditBlock;

const renderPanel = (onClose = vi.fn()) =>
  render(
    <MarkdownFieldPanel
      source="s"
      docId="s@main:notes/n1"
      edit={edit}
      block={block}
      onClose={onClose}
    />,
  );

test("test_markdown_field_panel", async () => {
  renderPanel();
  const editor = screen.getByRole("textbox", { name: "本文" });

  await userEvent.clear(editor);
  await userEvent.type(editor, "**太字**");

  expect(
    (usePendingEditsStore.getState().bySource.s ?? []).map(
      (item) => item.values,
    ),
  ).toEqual([{ "#items[i1].body": "**太字**" }]);
  await waitFor(() => expect(lastMarkdown()).toBe("**太字**"));
  expect(screen.getByText("変更あり")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "元に戻す" })).toBeInTheDocument();
});

test("test_markdown_field_panel_when_reverted", async () => {
  renderPanel();
  const editor = screen.getByRole("textbox", { name: "本文" });
  await userEvent.type(editor, "追記");

  await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));

  expect(screen.getByRole("textbox", { name: "本文" })).toHaveValue("**本文**");
  expect(usePendingEditsStore.getState().bySource.s ?? []).toHaveLength(0);
});

test("test_markdown_field_panel_when_closed", async () => {
  const onClose = vi.fn();
  renderPanel(onClose);
  const editor = screen.getByRole("textbox", { name: "本文" });
  await userEvent.type(editor, "追記");

  await userEvent.keyboard("{Escape}");

  expect(onClose).toHaveBeenCalled();
  expect(usePendingEditsStore.getState().bySource.s ?? []).toHaveLength(1);
});
