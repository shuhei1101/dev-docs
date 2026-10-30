import { QueryClient } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { createAppRouter, parseSearch, stringifySearch } from "@/app/router";

const createRouter = () =>
  createAppRouter({ queryClient: new QueryClient() });

test("test_create_app_router", () => {
  const router = createRouter();

  expect(router.options.defaultPreload).toBe("intent");
  expect(router.options.defaultPreloadStaleTime).toBe(0);
  expect(router.options.scrollRestoration).toBe(true);
});

test("test_parse_search_when_numeric_rev", () => {
  expect(parseSearch("?rev=8852552")).toEqual({ rev: "8852552" });
  expect(parseSearch("?rev=1234e5&base=abc1234")).toEqual({
    rev: "1234e5",
    base: "abc1234",
  });
});

test("test_stringify_search_when_numeric_rev", () => {
  expect(stringifySearch({ rev: "8852552", base: undefined })).toBe(
    "?rev=8852552",
  );
  expect(stringifySearch({})).toBe("");
});
