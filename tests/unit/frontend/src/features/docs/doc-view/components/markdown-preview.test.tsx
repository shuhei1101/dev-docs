import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";

const mount = vi.hoisted(() => vi.fn());

vi.mock(
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@develop/dist/index.js",
  () => ({ mount }),
);

const update = vi.hoisted(() => vi.fn());

beforeEach(() => {
  mount.mockReset();
  update.mockReset();
  mount.mockReturnValue({ update, destroy: vi.fn() });
});

test("test_markdown_preview", async () => {
  const { rerender } = render(
    <MarkdownPreview markdown="# A" docId="s@main:a" />,
  );
  await waitFor(() => expect(mount).toHaveBeenCalled());

  rerender(<MarkdownPreview markdown="# B" docId="s@main:a" />);

  await waitFor(() => expect(update).toHaveBeenLastCalledWith("# B", expect.anything()));
  const options = mount.mock.calls[0]?.[1] as {
    commentStore: { load: () => Promise<unknown[]> };
  };
  await expect(options.commentStore.load()).resolves.toEqual([]);
});
