import { expect, test, vi } from "vitest";

import { createQueryClient } from "@/app/query-client";
import { handleAppError } from "@/shared/core/handle-app-error";

vi.mock("@/shared/core/handle-app-error", () => ({ handleAppError: vi.fn() }));

test("test_create_query_client", () => {
  const options = createQueryClient().getDefaultOptions();

  expect(options.queries).toMatchObject({
    staleTime: 60000,
    refetchOnWindowFocus: false,
    retry: false,
  });
});

test("test_create_query_client_when_meta_off", async () => {
  const client = createQueryClient();

  await client
    .fetchQuery({
      queryKey: ["x"],
      queryFn: () => {
        throw new Error("failed");
      },
      meta: { handleError: false },
    })
    .catch(() => undefined);

  expect(handleAppError).not.toHaveBeenCalled();
});
