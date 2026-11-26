import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";

const mount = vi.hoisted(() => vi.fn());

vi.mock(
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@develop/dist/index.js",
  () => ({ mount }),
);

beforeEach(() => {
  mount.mockReset();
  mount.mockReturnValue({ update: vi.fn(), destroy: vi.fn() });
});

test("test_markdown_preview", async () => {
  const { rerender } = render(
    <MarkdownPreview markdown="# A" docId="s@main:a" />,
  );
  await waitFor(() => expect(mount).toHaveBeenCalled());

  rerender(<MarkdownPreview markdown="# B" docId="s@main:a" />);

  await waitFor(() =>
    expect(
      (mount.mock.calls.at(-1)?.[1] as { markdown: string }).markdown,
    ).toBe("# B"),
  );
  const options = mount.mock.calls.at(-1)?.[1] as {
    commentStore: { list: () => Promise<unknown[]> };
  };
  await expect(options.commentStore.list()).resolves.toEqual([]);
});
