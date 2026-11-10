import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { DocBody } from "@/features/docs/doc-view/components/doc-body";
import { docIdOf, useCommentStore } from "@/features/docs/shared/comments/comment-store";
import { documentResponse } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const mount = vi.hoisted(() => vi.fn());

vi.mock("https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@master/dist/index.js", () => ({ mount }));

const handle = () => ({
  update: vi.fn(),
  destroy: vi.fn(),
  reloadComments: vi.fn(() => Promise.resolve()),
  focusComment: vi.fn(),
});

const comment = (docId: string, id: string) => ({
  id,
  docId,
  source: "s",
  ref: null,
  path: "a.md",
  docTitle: "A",
  headings: [],
  quote: "x",
  prefix: "",
  suffix: "",
  body: "本文",
  selected: true,
  createdAt: "2026-11-04T00:00:00.000Z",
});

beforeEach(() => {
  mount.mockReset();
  mount.mockReturnValue(handle());
  useCommentStore.setState({ comments: [] });
});

test("test_doc_body", async () => {
  const document = documentResponse({
    markdown:
      "# A\n\n<!-- table: data +columns -->\n\n| 名前 | 備考 |\n| --- | --- |\n| x | y |\n\n<!-- /table -->\n",
    tableKeys: ["t1"],
    columns: { t1: ["備考"] },
  });

  renderInRouter(
    <DocBody document={document as never} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={null} onLocated={vi.fn()} />,
  );

  await waitFor(() => expect(mount).toHaveBeenCalled());
  const options = mount.mock.calls[0][1] as { markdown: string };
  expect(options.markdown).not.toContain("# A");
  expect(options.markdown).toContain("hide=備考");
});

test("test_doc_body_when_internal_link", async () => {
  mount.mockImplementation((element: HTMLElement) => {
    element.innerHTML = '<a href="./b.md">B</a>';
    return { update: vi.fn(), destroy: vi.fn() };
  });
  const { router } = renderInRouter(
    <DocBody document={documentResponse() as never} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={null} onLocated={vi.fn()} />,
    "/s/a.md?rev=v1",
  );

  await act(async () => {
    await userEvent.click(await screen.findByRole("link", { name: "B" }));
  });

  await waitFor(() => expect(router.state.location.pathname).toBe("/s/b.md"));
  expect(router.state.location.search).toMatchObject({ rev: "v1" });
});

test("test_doc_body_when_body_path", async () => {
  mount.mockImplementation((element: HTMLElement) => {
    element.innerHTML = '<a href="./b.md">B</a>';
    return { update: vi.fn(), destroy: vi.fn() };
  });
  const document = documentResponse({ path: "notes/files/a", bodyPath: "notes/a.md" });
  const { router } = renderInRouter(
    <DocBody document={document as never} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={null} onLocated={vi.fn()} />,
    "/s/notes/files/a?rev=v1",
  );

  await act(async () => {
    await userEvent.click(await screen.findByRole("link", { name: "B" }));
  });

  await waitFor(() => expect(router.state.location.pathname).toBe("/s/notes/b.md"));
  expect(router.state.location.search).toMatchObject({ rev: "v1" });
});

test("test_doc_body_when_base", async () => {
  const document = documentResponse({ tableKeys: ["t1"], columns: { t1: ["備考"] } });
  const baseMarkdown = {
    markdown:
      "# A\n\n<!-- table: data +columns -->\n\n| 名前 | 備考 |\n| --- | --- |\n| x | z |\n\n<!-- /table -->\n",
    tableKeys: ["t1"],
  };

  renderInRouter(
    <DocBody document={document as never} baseMarkdown={baseMarkdown} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={null} onLocated={vi.fn()} />,
  );

  await waitFor(() => expect(mount).toHaveBeenCalled());
  const options = mount.mock.calls[0][1] as { baseMarkdown: string };
  expect(options.baseMarkdown).not.toContain("# A");
  expect(options.baseMarkdown).toContain("hide=備考");
});

test("test_doc_body_when_comments_changed", async () => {
  const document = documentResponse();
  const docId = docIdOf(document as never);
  useCommentStore.setState({ comments: [comment(docId, "c1"), comment(docId, "c2")] });
  const current = handle();
  mount.mockReturnValue(current);

  renderInRouter(
    <DocBody document={document as never} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={null} onLocated={vi.fn()} />,
  );
  await waitFor(() => expect(mount).toHaveBeenCalled());
  current.reloadComments.mockClear();
  act(() => useCommentStore.getState().remove("c1"));

  await waitFor(() => expect(current.reloadComments).toHaveBeenCalledTimes(1));
});

test("test_doc_body_when_locating", async () => {
  const document = documentResponse();
  const docId = docIdOf(document as never);
  const current = handle();
  mount.mockReturnValue(current);
  const onLocated = vi.fn();

  renderInRouter(
    <DocBody document={document as never} onHeadings={vi.fn()} onCommentSaved={vi.fn()} locating={comment(docId, "c1")} onLocated={onLocated} />,
  );

  await waitFor(() => expect(current.focusComment).toHaveBeenCalledWith("c1"));
  expect(current.reloadComments.mock.invocationCallOrder[0]).toBeLessThan(
    current.focusComment.mock.invocationCallOrder[0],
  );
  expect(current.focusComment).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(onLocated).toHaveBeenCalledTimes(1));
});
