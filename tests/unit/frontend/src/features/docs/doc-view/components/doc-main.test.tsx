import { screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { DocMain } from "@/features/docs/doc-view/components/doc-main";
import { documentResponse, page, refsResponse } from "@tests/helpers/fixtures";
import { renderInRouter } from "@tests/helpers/render";

vi.mock("@/features/docs/doc-view/components/doc-body", () => ({
  DocBody: () => <div data-testid="doc-body" />,
}));

const renderDocMain = (doc: ReturnType<typeof documentResponse>, emptyTab: unknown = null) =>
  renderInRouter(
    <DocMain
      doc={doc as never}
      active={{ tab: doc.tabs[0], group: "設計", page: page("A", "a.md") } as never}
      search={{}}
      refs={refsResponse() as never}
      emptyTab={emptyTab as never}
      busy={false}
      onHeadings={vi.fn()}
      onCommentSaved={vi.fn()}
      locating={null}
      onLocated={vi.fn()}
      onRetry={vi.fn()}
      onCompare={vi.fn()}
      onClearDiff={vi.fn()}
    />,
  );

test("test_doc_main", async () => {
  renderDocMain(documentResponse());

  expect(await screen.findByRole("navigation", { name: "パンくず" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "A" })).toBeInTheDocument();
  expect(screen.getByTestId("doc-body")).toBeInTheDocument();
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");
});

test("test_doc_main_when_empty_tab", async () => {
  const doc = documentResponse();

  renderDocMain(doc, doc.tabs[1]);

  expect(await screen.findByRole("heading", { level: 1, name: "規約" })).toBeInTheDocument();
  expect(screen.getByText("規約の文書はありません")).toBeInTheDocument();
  expect(screen.queryByTestId("doc-body")).toBeNull();
});

test("test_doc_main_when_conversion_error", async () => {
  renderDocMain(
    documentResponse({
      conversionError: { reason: "timeout", kind: "rules", script: "scripts/convert.py", detail: "x" },
    }),
  );

  expect(await screen.findByText("本文を変換できませんでした")).toBeInTheDocument();
  expect(screen.queryByTestId("doc-body")).toBeNull();
});

test("test_doc_main_when_diff", async () => {
  renderDocMain(documentResponse({ diff: { base: "7c0aa11" } }));

  expect(await screen.findByRole("region", { name: "差分" })).toBeInTheDocument();
});
