import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { DocEditBar } from "@/features/docs/doc-view/components/doc-edit-bar";
import { upsertBodyEdit } from "@/features/docs/doc-view/edit";
import type { DocumentEdit } from "@/shared/api/generated/model";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit } from "@tests/helpers/fixtures";

const yamlEdit = docEdit() as unknown as DocumentEdit;

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

test("test_doc_edit_bar", async () => {
  const onModeChange = vi.fn();
  render(
    <DocEditBar
      source="s"
      edit={yamlEdit}
      mode={undefined}
      onModeChange={onModeChange}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "編集" }));

  expect(onModeChange).toHaveBeenCalledWith("fields");
});

test("test_doc_edit_bar_when_markdown", async () => {
  const onModeChange = vi.fn();
  const markdownEdit = docEdit({
    language: "markdown",
    blocks: [],
    titleBlock: null,
  }) as unknown as DocumentEdit;
  const { rerender } = render(
    <DocEditBar
      source="s"
      edit={markdownEdit}
      mode={undefined}
      onModeChange={onModeChange}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: "編集" }));
  rerender(
    <DocEditBar
      source="s"
      edit={markdownEdit}
      mode="file"
      onModeChange={onModeChange}
    />,
  );

  expect(onModeChange).toHaveBeenCalledWith("file");
  expect(
    screen.queryByRole("button", { name: "表示した場所で修正" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "編集を終了" }),
  ).toBeInTheDocument();
});

test("test_doc_edit_bar_when_other_mode_pending", () => {
  upsertBodyEdit("s", yamlEdit, {
    path: "summary",
    label: "概要",
    before: "x",
    value: "y",
  });

  render(
    <DocEditBar
      source="s"
      edit={yamlEdit}
      mode="fields"
      onModeChange={() => {}}
    />,
  );

  expect(
    screen.getByRole("button", { name: "表示した場所で修正" }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "ファイル全体" })).toBeDisabled();
  expect(
    screen.getByText(
      "表示した場所で修正の変更をコミットするか元に戻すと切り替えられます。",
    ),
  ).toBeInTheDocument();
});
