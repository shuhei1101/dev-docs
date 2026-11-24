import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { createTestQueryClient } from "@tests/helpers/render";
import { server } from "@tests/helpers/msw-server";
import { QueryClientProvider } from "@tanstack/react-query";

const items = [
  { path: "docs/a", name: "文書 A", snippets: ["…foo の説明…"] },
  { path: "docs/b", name: "文書 B", snippets: ["…foo の例…"] },
];

const renderDialog = (onResultSelect = vi.fn()) => {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <SearchDialog
        open
        onOpenChange={vi.fn()}
        source="s"
        ref="main"
        onResultSelect={onResultSelect}
      />
    </QueryClientProvider>,
  );
  return onResultSelect;
};

test("test_search_dialog", async () => {
  const search = vi.fn(() => HttpResponse.json({ totalCount: 2, items }));
  server.use(http.get("/_api/sources/s/search", search));
  const onResultSelect = renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");
  await screen.findByText("文書 A");
  await userEvent.keyboard("{Enter}");

  await waitFor(() => expect(onResultSelect).toHaveBeenCalledTimes(1));
  expect(onResultSelect).toHaveBeenCalledWith("docs/a");
  expect(search).toHaveBeenCalled();
});

test("test_search_dialog_when_empty_query", async () => {
  const search = vi.fn(() => HttpResponse.json({ totalCount: 0, items: [] }));
  server.use(http.get("/_api/sources/s/search", search));

  renderDialog();
  await new Promise((resolve) => setTimeout(resolve, 400));

  expect(search).not.toHaveBeenCalled();
});

test("test_search_dialog_when_excluded_count", async () => {
  server.use(
    http.get("/_api/sources/s/search", () =>
      HttpResponse.json({ totalCount: 2, items, excludedCount: 1 }),
    ),
  );
  renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");

  expect(
    await screen.findByText("2 件（リビジョン main）・検索から除外 1 件"),
  ).toBeInTheDocument();
});

test("test_search_dialog_when_only_excluded", async () => {
  server.use(
    http.get("/_api/sources/s/search", () =>
      HttpResponse.json({ totalCount: 0, items: [], excludedCount: 1 }),
    ),
  );
  renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");

  expect(
    await screen.findByText(
      "該当する文書はありません。検索から除外した文書を含めると 1 件あります。",
    ),
  ).toBeInTheDocument();
});

test("test_search_dialog_when_include_excluded", async () => {
  const queries: URLSearchParams[] = [];
  server.use(
    http.get("/_api/sources/s/search", ({ request }) => {
      const params = new URL(request.url).searchParams;
      queries.push(params);
      return params.get("include_excluded") === "true"
        ? HttpResponse.json({
            totalCount: 3,
            items: [
              ...items,
              { path: "docs/c", name: "文書 C", snippets: [], excluded: true },
            ],
          })
        : HttpResponse.json({ totalCount: 2, items, excludedCount: 1 });
    }),
  );
  renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");
  await screen.findByText("文書 A");
  await userEvent.click(
    screen.getByRole("switch", { name: "検索から除外した文書も含める" }),
  );

  expect(await screen.findAllByText("検索から除外")).toHaveLength(1);
  expect(queries.at(-1)?.get("include_excluded")).toBe("true");
  expect(queries[0]?.get("include_excluded")).toBeNull();
});
