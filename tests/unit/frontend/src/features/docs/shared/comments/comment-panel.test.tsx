import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, test, vi } from "vitest";

import { CommentPanel } from "@/features/docs/shared/comments/comment-panel";
import { useCommentStore } from "@/features/docs/shared/comments/comment-store";

vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }) }));

const writeText = vi.fn();

const addThree = () => {
  const { add } = useCommentStore.getState();
  for (const body of ["一つ目", "二つ目", "三つ目"]) {
    add({
      docId: "s@main:a.md",
      source: "s",
      ref: "main",
      path: "a.md",
      docTitle: "A",
      headings: [],
      quote: `引用 ${body}`,
      prefix: "",
      suffix: "",
      body,
    });
  }
};

const renderPanel = () =>
  render(
    <CommentPanel open onOpenChange={vi.fn()} github={null} onLocate={vi.fn()} />,
  );

beforeEach(() => {
  vi.clearAllMocks();
  writeText.mockReset();
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  useCommentStore.setState({ comments: [] });
  addThree();
});

test("test_comment_panel", async () => {
  writeText.mockResolvedValue(undefined);
  renderPanel();
  await userEvent.click(screen.getByRole("checkbox", { name: "2 件目を選択" }));

  await userEvent.click(screen.getByRole("button", { name: "選択 2 件をコピー" }));

  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  const text = writeText.mock.calls[0][0] as string;
  expect(text).toContain("一つ目");
  expect(text).not.toContain("二つ目");
  expect(text).toContain("三つ目");
  await waitFor(() =>
    expect(toast.success).toHaveBeenCalledWith("選択 2 件をクリップボードにコピーしました。"),
  );
});

test("test_comment_panel_when_indeterminate", async () => {
  renderPanel();
  await act(async () => useCommentStore.getState().setSelected(null, false));
  await userEvent.click(screen.getByRole("checkbox", { name: "1 件目を選択" }));

  expect(screen.getByRole("checkbox", { name: "すべて選択" })).toHaveAttribute("aria-checked", "mixed");
});

test("test_comment_panel_when_clipboard_failed", async () => {
  writeText.mockRejectedValue(new Error("denied"));
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "選択 3 件をコピー" }));

  await waitFor(() =>
    expect(toast.error).toHaveBeenCalledWith("クリップボードにコピーできませんでした。"),
  );
});

test("test_comment_panel_when_deleted", async () => {
  const before = useCommentStore.getState().comments;
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "2 件目のコメントを削除" }));

  expect(useCommentStore.getState().comments).toHaveLength(2);
  expect(toast).toHaveBeenCalledTimes(1);
  const [message, options] = vi.mocked(toast).mock.calls[0] as unknown as [
    string,
    { action: { label: string; onClick: () => void } },
  ];
  expect(message).toBe("コメントを削除しました。");
  expect(options.action.label).toBe("元に戻す");

  act(() => options.action.onClick());

  expect(useCommentStore.getState().comments).toEqual(before);
});

test("test_comment_panel_when_accessible_name", () => {
  useCommentStore.setState({ comments: useCommentStore.getState().comments.slice(0, 2) });
  renderPanel();

  expect(screen.getByRole("button", { name: "2 件目のコメントを修正" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "2 件目のコメントを削除" })).toBeInTheDocument();
});
