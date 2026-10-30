import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";
import type { ReactNode } from "react";

import { useSourceForm } from "@/features/settings/settings/hooks/use-source-form";
import {
  PROBLEM_HEADERS,
  problem,
  settingsSource,
} from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const sources = [settingsSource("a")];

const setup = (onSaved = vi.fn()) => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={createTestQueryClient()}>
      {children}
    </QueryClientProvider>
  );
  const view = renderHook(
    () => useSourceForm({ sources: sources as never, index: null, onSaved }),
    {
      wrapper,
    },
  );
  act(() => {
    view.result.current.form.reset({
      id: "extra",
      config: "/x/dev-docs.yaml",
      enabled: true,
      read: "/x/**",
      write: "",
    });
  });
  return { ...view, onSaved };
};

test("test_use_source_form", async () => {
  let body = null as { sources: { id: string }[] } | null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({
        sources: [{ id: "extra", status: "serving", errors: [] }],
      });
    }),
  );
  const { result, onSaved } = setup();

  await act(async () => result.current.submit());

  expect(body?.sources.map((item) => item.id)).toEqual(["a", "extra"]);
  expect(onSaved).toHaveBeenCalledTimes(1);
});

test("test_use_source_form_when_422", async () => {
  server.use(
    http.put("/_api/settings/sources", () =>
      HttpResponse.json(
        problem(422, {
          errors: [
            { path: "sources[1].config[0]", reason: "ファイルがありません" },
          ],
        }),
        { status: 422, headers: PROBLEM_HEADERS },
      ),
    ),
  );
  const { result, onSaved } = setup();

  await act(async () => result.current.submit());

  await waitFor(() => expect(result.current.summary).toHaveLength(1));
  expect(result.current.form.formState.errors.config?.message).toBe(
    "ファイルがありません",
  );
  expect(onSaved).not.toHaveBeenCalled();
});
