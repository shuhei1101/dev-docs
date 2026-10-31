import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { DocBody } from "@/features/docs/doc-view/components/doc-body";
import { documentResponse } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

const mount = vi.hoisted(() => vi.fn());

vi.mock("https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@master/dist/index.js", () => ({ mount }));

beforeEach(() => {
  mount.mockReset();
  mount.mockReturnValue({ update: vi.fn(), destroy: vi.fn() });
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
