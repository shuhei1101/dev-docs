import { isNotFound } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import {
  baseMarkdownQueryOptions,
  documentQueryOptions,
  loadDocument,
} from "@/features/docs/doc-view/queries";
import { PROBLEM_HEADERS, documentResponse, problem } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const run = (options: { queryFn?: unknown }, queryClient = createTestQueryClient()) =>
  (options.queryFn as (context: unknown) => Promise<unknown>)({
    queryKey: [],
    signal: new AbortController().signal,
    client: queryClient,
    meta: undefined,
  });

test("test_document_query_options", async () => {
  const urls: string[] = [];
  server.use(
    http.get("/_api/sources/s/docs", ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json(documentResponse());
    }),
    http.get("/_api/sources/s/docs/a.md", ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json(documentResponse());
    }),
  );

  await run(documentQueryOptions("s", "", { rev: "v2", base: "v1" }));
  await run(documentQueryOptions("s", "a.md", { rev: "v2", base: "v1" }));

  expect(urls).toHaveLength(2);
  expect(new URL(urls[0]).pathname).toBe("/_api/sources/s/docs");
  expect(new URL(urls[1]).pathname).toBe("/_api/sources/s/docs/a.md");
  for (const url of urls) {
    expect(new URL(url).searchParams.get("ref")).toBe("v2");
    expect(new URL(url).searchParams.get("diff")).toBe("v1");
  }
});

test("test_base_markdown_query_options", async () => {
  server.use(
    http.get("/_api/sources/s/docs/a.md", ({ request }) =>
      new URL(request.url).searchParams.get("ref") === "v1"
        ? HttpResponse.json(documentResponse({ markdown: "# A" }))
        : HttpResponse.json(documentResponse()),
    ),
  );

  expect(await run(baseMarkdownQueryOptions("s", "a.md", "v1"))).toBe("# A");
});

test("test_base_markdown_query_options_when_added", async () => {
  server.use(
    http.get("/_api/sources/s/docs/a.md", () =>
      HttpResponse.json(problem(404, { missing: { kind: "doc", source: "s", ref: "v1", path: "a.md" } }), {
        status: 404,
        headers: PROBLEM_HEADERS,
      }),
    ),
  );

  expect(await run(baseMarkdownQueryOptions("s", "a.md", "v1"))).toBeNull();
});

test("test_load_document_when_not_found", async () => {
  server.use(
    http.get("/_api/sources/s/docs/a.md", () =>
      HttpResponse.json(problem(404, { missing: { kind: "doc", source: "s", ref: "main", path: "a.md" } }), {
        status: 404,
        headers: PROBLEM_HEADERS,
      }),
    ),
  );

  const caught = await loadDocument({
    context: { queryClient: createTestQueryClient() },
    params: { source: "s", _splat: "a.md" },
    deps: {},
  } as never).catch((error: unknown) => error);

  expect(isNotFound(caught)).toBe(true);
  expect((caught as { data: { missing: { kind: string } } }).data.missing.kind).toBe("doc");
});
