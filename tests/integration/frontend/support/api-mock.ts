import type { Page } from "@playwright/test";

import {
  documentResponse,
  refsResponse,
  searchResult,
  settingsView,
} from "./fixtures";

export type ApiRequest = {
  source: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
};

export type Reply = { status?: number; body: unknown; delayMs?: number };

export type Operation =
  | "document"
  | "refs"
  | "search"
  | "putColumns"
  | "settings"
  | "putSettings";

export type Handler = (request: ApiRequest) => Reply;

export type Call = { operation: Operation; request: ApiRequest };

export type ApiMock = {
  calls: Call[];
  callsOf: (operation: Operation) => Call[];
};

/** problem+json の本文を持つ失敗の応答 */
export const problem = (
  status: number,
  extra: Record<string, unknown> = {},
): Reply => ({
  status,
  body: {
    type: "urn:dev-docs:error:Error",
    title: "Error",
    status,
    detail: "失敗しました",
    nextSteps: [],
    ...extra,
  },
});

const defaults: Record<Operation, Handler> = {
  document: ({ source, path, query }) => ({
    body: documentResponse({
      source,
      path: path === "" ? "docs/doc-1" : path,
      ref: query.get("ref") ?? "develop",
    }),
  }),
  refs: () => ({ body: refsResponse() }),
  search: () => ({ body: searchResult() }),
  putColumns: ({ body }) => ({ body }),
  settings: () => ({ body: settingsView() }),
  putSettings: () => ({ body: { sources: [] } }),
};

const ROUTES: { operation: Operation; method: string; pattern: RegExp }[] = [
  {
    operation: "document",
    method: "GET",
    pattern: /^\/_api\/sources\/([^/]+)\/docs(?:\/(.*))?$/,
  },
  {
    operation: "refs",
    method: "GET",
    pattern: /^\/_api\/sources\/([^/]+)\/refs$/,
  },
  {
    operation: "search",
    method: "GET",
    pattern: /^\/_api\/sources\/([^/]+)\/search$/,
  },
  {
    operation: "putColumns",
    method: "PUT",
    pattern: /^\/_api\/sources\/([^/]+)\/columns$/,
  },
  {
    operation: "settings",
    method: "GET",
    pattern: /^\/_api\/settings\/sources$/,
  },
  {
    operation: "putSettings",
    method: "PUT",
    pattern: /^\/_api\/settings\/sources$/,
  },
];

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** 画面の API(`/_api/`)を、ページ単位で差し替える。`overrides` で操作ごとの応答を替える */
export const mockApi = async (
  page: Page,
  overrides: Partial<Record<Operation, Handler>> = {},
): Promise<ApiMock> => {
  const calls: Call[] = [];
  await page.route("**/_api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const matched = ROUTES.find(
      (item) =>
        item.method === request.method() && item.pattern.test(url.pathname),
    );
    if (!matched) {
      await route.fulfill({
        status: 404,
        contentType: "application/problem+json",
        body: JSON.stringify(problem(404).body),
      });
      return;
    }
    const groups = matched.pattern.exec(url.pathname) ?? [];
    const apiRequest: ApiRequest = {
      source: decodeURIComponent(groups[1] ?? ""),
      path: decodeURIComponent(groups[2] ?? ""),
      query: url.searchParams,
      body: request.postDataJSON() as unknown,
    };
    calls.push({ operation: matched.operation, request: apiRequest });
    const handler = overrides[matched.operation] ?? defaults[matched.operation];
    const reply = handler(apiRequest);
    if (reply.delayMs !== undefined) await wait(reply.delayMs);
    const status = reply.status ?? 200;
    await route.fulfill({
      status,
      contentType: status >= 400 ? "application/problem+json" : "application/json",
      body: JSON.stringify(reply.body),
    });
  });
  return {
    calls,
    callsOf: (operation) => calls.filter((call) => call.operation === operation),
  };
};
