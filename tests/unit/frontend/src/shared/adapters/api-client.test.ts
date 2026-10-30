import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import { PROBLEM_HEADERS, problem } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { apiClient } from "@/shared/adapters/api-client";
import { AppError, VersionConflictError } from "@/shared/core/app-error";

test("test_api_client", async () => {
  server.use(http.get("/_api/x", () => HttpResponse.json({ a: 1 })));

  expect(await apiClient("/_api/x")).toEqual({ a: 1 });
});

test("test_api_client_when_problem", async () => {
  server.use(
    http.get("/_api/x", () =>
      HttpResponse.json(problem(409), { status: 409, headers: PROBLEM_HEADERS }),
    ),
  );

  await expect(apiClient("/_api/x")).rejects.toBeInstanceOf(VersionConflictError);
});

test("test_api_client_when_network_error", async () => {
  server.use(http.get("/_api/x", () => HttpResponse.error()));

  const error = await apiClient("/_api/x").catch((caught: unknown) => caught);

  expect(error).toBeInstanceOf(AppError);
  expect((error as AppError).status).toBe(0);
});
