import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";

import { WholeFileEditor } from "@/features/docs/doc-view/components/whole-file-editor";
import type { DocumentEdit } from "@/shared/api/generated/model";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

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

const renderEditor = (
  edit: DocumentEdit = docEdit() as unknown as DocumentEdit,
) =>
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <WholeFileEditor
        source="s"
        path="notes/n1"
        docId="s@main:notes/n1"
        markdown="# n1"
        edit={edit}
      />
    </QueryClientProvider>,
  );

const preview = (body: Record<string, unknown>, calls: unknown[] = []) =>
  server.use(
    http.post("/_api/sources/s/preview", async ({ request }) => {
      calls.push(await request.json());
      return HttpResponse.json({
        markdown: null,
        conversionError: null,
        fallback: false,
        ...body,
      });
    }),
  );

test("test_whole_file_editor", async () => {
  const calls: unknown[] = [];
  preview({ markdown: "# n1\n\n修正後の概要" }, calls);
  renderEditor();
  const editor = screen.getByRole("textbox", { name: "notes/n1.yaml" });

  await userEvent.clear(editor);
  await userEvent.type(editor, "title: n1{Enter}summary: 修正後の概要");

  expect(
    (usePendingEditsStore.getState().bySource.s ?? []).map((item) =>
      Object.keys(item.values),
    ),
  ).toEqual([["@file"]]);
  await waitFor(() => expect(lastMarkdown()).toBe("# n1\n\n修正後の概要"));
  expect(calls).toHaveLength(1);
});

test("test_whole_file_editor_when_invalid", async () => {
  preview({
    conversionError: {
      reason: "invalid_yaml",
      kind: "note",
      detail: "found character '\\t'",
      file: "notes/n1.yaml",
      line: 3,
      column: 1,
    },
  });
  renderEditor();
  const editor = screen.getByRole("textbox", { name: "notes/n1.yaml" });

  await userEvent.type(editor, "{Enter}\tstatus: draft");

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("YAML として解析できません");
  expect(alert).toHaveTextContent("3 行 1 列:");
  expect(editor).toHaveAttribute("aria-invalid", "true");
  expect(lastMarkdown()).toBe("# n1");
});

test("test_whole_file_editor_when_fallback", async () => {
  preview({ markdown: "# n1", fallback: true });
  renderEditor();

  await userEvent.type(
    screen.getByRole("textbox", { name: "notes/n1.yaml" }),
    " ",
  );

  expect(
    await screen.findByText(
      "この種類のプレビューは、配信元の変換を使用できないため標準の変換で表示しています。",
    ),
  ).toBeInTheDocument();
});

test("test_whole_file_editor_when_markdown", async () => {
  const calls: unknown[] = [];
  preview({}, calls);
  renderEditor(
    docEdit({
      language: "markdown",
      filePath: "guide.md",
      source: "# ガイド\n",
      blocks: [],
      titleBlock: null,
    }) as unknown as DocumentEdit,
  );
  const editor = screen.getByRole("textbox", { name: "guide.md" });

  await userEvent.type(editor, "追記");

  await waitFor(() => expect(lastMarkdown()).toBe("# ガイド\n追記"));
  expect(calls).toHaveLength(0);
});
