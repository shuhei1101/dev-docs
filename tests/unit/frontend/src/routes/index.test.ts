import { isRedirect } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import { createTestQueryClient } from "@tests/helpers/render";
import { settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { redirectToFirstSource } from "@/routes/index";

const redirectOf = async () => {
  const caught = await redirectToFirstSource({
    context: { queryClient: createTestQueryClient() },
  } as never).catch((error: unknown) => error);
  expect(isRedirect(caught)).toBe(true);
  return caught as { options: { to: string; params?: Record<string, string> } };
};

test("test_redirect_to_first_source", async () => {
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(
        settingsView([
          settingsSource("a", { status: "not_served" }),
          settingsSource("b", { status: "serving" }),
        ]),
      ),
    ),
  );

  const redirect = await redirectOf();

  expect(redirect.options.to).toBe("/$source");
  expect(redirect.options.params).toEqual({ source: "b" });
});

test("test_redirect_to_first_source_when_none", async () => {
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView([])),
    ),
  );

  const redirect = await redirectOf();

  expect(redirect.options.to).toBe("/_settings");
});
