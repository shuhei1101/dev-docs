import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, delay, http } from "msw";
import { expect, test, vi } from "vitest";

import { SearchDialog } from "@/features/docs/shared/search-dialog/search-dialog";
import { createTestQueryClient } from "@tests/helpers/render";
import { server } from "@tests/helpers/msw-server";
import { QueryClientProvider } from "@tanstack/react-query";

const items = [
  { path: "docs/a", name: "文書 A", snippets: ["…foo の説明…"] },
  { path: "docs/b", name: "文書 B", snippets: ["…foo の例…"] },
];

type DialogOptions = {
  sources?: string[];
  unavailable?: { source: string; reason: string }[];
};

const renderDialog = (
  onResultSelect = vi.fn(),
  { sources, unavailable }: DialogOptions = {},
) => {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <SearchDialog
        open
        onOpenChange={vi.fn()}
        source="s"
        ref="main"
        sources={sources}
        unavailable={unavailable}
        onResultSelect={onResultSelect}
      />
    </QueryClientProvider>,
  );
  return onResultSelect;
};

/** 単語を入力し、検索の範囲を全ての配信元にする */
const searchAllSources = async () => {
  await userEvent.type(screen.getByRole("combobox"), "foo");
  await userEvent.click(screen.getByRole("radio", { name: "全ての配信元" }));
};

test("test_search_dialog", async () => {
  const search = vi.fn(() => HttpResponse.json({ totalCount: 2, items }));
  server.use(http.get("/_api/sources/s/search", search));
  const onResultSelect = renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");
  await screen.findByText("文書 A");
  await userEvent.keyboard("{Enter}");

  await waitFor(() => expect(onResultSelect).toHaveBeenCalledTimes(1));
  expect(onResultSelect).toHaveBeenCalledWith("docs/a", "s");
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
      "該当する文書はありません。配信元の設定で検索から除外した文書を含めると 1 件あります。",
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
    screen.getByRole("switch", {
      name: "配信元の設定で検索から除外した文書も含める",
    }),
  );

  expect(await screen.findAllByText("検索から除外")).toHaveLength(1);
  expect(queries.at(-1)?.get("include_excluded")).toBe("true");
  expect(queries[0]?.get("include_excluded")).toBeNull();
});

test("test_search_dialog_when_all_sources", async () => {
  const queries: { source: string; params: URLSearchParams }[] = [];
  server.use(
    http.get("/_api/sources/:source/search", ({ params, request }) => {
      const source = String(params.source);
      queries.push({ source, params: new URL(request.url).searchParams });
      return HttpResponse.json(
        source === "t"
          ? {
              totalCount: 1,
              items: [{ path: "docs/t", name: "文書 T", snippets: [] }],
            }
          : { totalCount: 2, items },
      );
    }),
  );
  const onResultSelect = renderDialog(vi.fn(), { sources: ["s", "t"] });

  await searchAllSources();
  expect(await screen.findByText("3 件")).toBeInTheDocument();
  const row = screen.getByRole("option", { name: /文書 T/ });
  expect(row).toHaveTextContent("t");
  await userEvent.click(row);

  expect(onResultSelect).toHaveBeenCalledWith("docs/t", "t");
  const allQueries = queries.filter((query) => query.params.get("q") === "foo");
  expect(new Set(allQueries.map((query) => query.source))).toEqual(
    new Set(["s", "t"]),
  );
  expect(
    allQueries
      .filter((query) => query.source === "t")
      .every((query) => query.params.get("ref") === null),
  ).toBe(true);
});

test("test_search_dialog_when_sorted", async () => {
  server.use(
    http.get("/_api/sources/s/search", () =>
      HttpResponse.json({
        totalCount: 3,
        items: [
          { path: "docs/c", name: "文書 C", snippets: [], matchCount: null },
          { path: "docs/a", name: "文書 A", snippets: [], matchCount: 2 },
          { path: "docs/b", name: "文書 B", snippets: [], matchCount: 9 },
        ],
      }),
    ),
  );
  renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");
  await screen.findByText("文書 C");
  const names = () =>
    screen.getAllByRole("option").map((option) => option.textContent ?? "");

  expect(names()[0]).toContain("文書 B");
  expect(names()[1]).toContain("文書 A");
  expect(names()[2]).toContain("文書 C");
  expect(names()[2]).not.toMatch(/一致 \d+ 行/);
  expect(names()[0]).toContain("一致 9 行");

  await userEvent.click(screen.getByRole("radio", { name: "名前" }));
  expect(names().map((name) => name.slice(0, 4))).toEqual([
    "文書 A",
    "文書 B",
    "文書 C",
  ]);
});

test("test_search_dialog_when_source_failed", async () => {
  const requested: string[] = [];
  server.use(
    http.get("/_api/sources/:source/search", ({ params }) => {
      const source = String(params.source);
      requested.push(source);
      return source === "t"
        ? HttpResponse.json(
            {
              type: "about:blank",
              title: "Service Unavailable",
              status: 503,
              detail: "project-index に接続できませんでした。",
            },
            {
              status: 503,
              headers: { "Content-Type": "application/problem+json" },
            },
          )
        : HttpResponse.json({ totalCount: 2, items });
    }),
  );
  renderDialog(vi.fn(), {
    sources: ["s", "t"],
    unavailable: [
      { source: "broken", reason: "配信元の設定の検証に通りません。" },
    ],
  });

  await searchAllSources();
  const failures = await screen.findByRole("list", {
    name: "検索できなかった配信元",
  });

  await waitFor(() =>
    expect(failures).toHaveTextContent(
      "project-index に接続できませんでした。",
    ),
  );
  expect(failures).toHaveTextContent("broken");
  expect(failures).toHaveTextContent("配信元の設定の検証に通りません。");
  expect(screen.getByText("文書 A")).toBeInTheDocument();
  expect(requested).not.toContain("broken");
});

test("test_search_dialog_when_pending_source", async () => {
  server.use(
    http.get("/_api/sources/:source/search", async ({ params }) => {
      if (params.source === "t") await delay("infinite");
      return HttpResponse.json({ totalCount: 2, items });
    }),
  );
  renderDialog(vi.fn(), { sources: ["s", "t"] });

  await searchAllSources();

  expect(
    await screen.findByText("2 件・1 件の配信元を検索しています"),
  ).toBeInTheDocument();
  expect(screen.getByText("文書 A")).toBeInTheDocument();
});

test("test_search_dialog_when_over_limit", async () => {
  const queries: URLSearchParams[] = [];
  const many = Array.from({ length: 100 }, (_, index) => ({
    path: `docs/${index}`,
    name: `文書 ${index}`,
    snippets: [],
  }));
  server.use(
    http.get("/_api/sources/s/search", ({ request }) => {
      queries.push(new URL(request.url).searchParams);
      return HttpResponse.json({ totalCount: 150, items: many });
    }),
  );
  renderDialog();

  await userEvent.type(screen.getByRole("combobox"), "foo");

  expect(
    await screen.findByText("150 件（リビジョン main）のうち 100 件を表示"),
  ).toBeInTheDocument();
  expect(queries.at(-1)?.get("limit")).toBe("100");
});
