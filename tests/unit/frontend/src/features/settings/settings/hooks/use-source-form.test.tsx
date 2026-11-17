import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";
import type { ReactNode } from "react";

import { useSourceForm } from "@/features/settings/settings/hooks/use-source-form";
import { PROBLEM_HEADERS, problem, settingsSource } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const sources = [settingsSource("a")];

const setup = (onSaved = vi.fn()) => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
  const view = renderHook(() => useSourceForm({ sources: sources as never, index: null, onSaved }), {
    wrapper,
  });
  act(() => {
    view.result.current.form.reset({
      id: "extra",
      config: "/x/dev-docs.yaml",
      enabled: true,
      read: "/x/**",
      write: "",
      outsideRead: true,
    });
  });
  return { ...view, onSaved };
};

test("test_use_source_form", async () => {
  let body = null as { sources: { id: string }[] } | null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({ sources: [{ id: "extra", status: "serving", errors: [] }] });
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
        problem(422, { errors: [{ path: "sources[1].config[0]", reason: "ファイルがありません" }] }),
        { status: 422, headers: PROBLEM_HEADERS },
      ),
    ),
  );
  const { result, onSaved } = setup();

  await act(async () => result.current.submit());

  await waitFor(() => expect(result.current.summary).toHaveLength(1));
  expect(result.current.form.formState.errors.config?.message).toBe("ファイルがありません");
  expect(onSaved).not.toHaveBeenCalled();
});

const renderForm = (initial: unknown[], index: number) => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
  return renderHook(
    ({ rows }: { rows: unknown[] }) =>
      useSourceForm({ sources: rows as never, index, onSaved: vi.fn() }),
    { wrapper, initialProps: { rows: initial } },
  );
};

test("test_use_source_form_when_conflict", async () => {
  server.use(
    http.put("/_api/settings/sources", () =>
      HttpResponse.json(problem(409, { current: "v2" }), { status: 409, headers: PROBLEM_HEADERS }),
    ),
  );
  const { result, onSaved } = setup();

  await act(async () => result.current.submit());

  await waitFor(() => expect(result.current.conflict).toBe(true));
  expect(onSaved).not.toHaveBeenCalled();
  expect(result.current.form.getValues("id")).toBe("extra");
});

test("test_use_source_form_when_row_moved", async () => {
  let body = null as { sources: { id: string; config: string[] }[] } | null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({ sources: [] });
    }),
  );
  const view = renderForm([settingsSource("a"), settingsSource("b")], 1);
  act(() => view.result.current.form.setValue("config", "/new/dev-docs.yaml"));

  view.rerender({ rows: [settingsSource("c"), settingsSource("a"), settingsSource("b")] });
  await act(async () => view.result.current.submit());

  expect(body?.sources.map((item) => item.id)).toEqual(["c", "a", "b"]);
  expect(body?.sources[2].config).toEqual(["/new/dev-docs.yaml"]);
  expect(body?.sources[0].config).toEqual(["/home/me/c/dev-docs.yaml"]);
});

test("test_use_source_form_when_gone", async () => {
  const save = vi.fn(() => HttpResponse.json({ sources: [] }));
  server.use(http.put("/_api/settings/sources", save));
  const view = renderForm([settingsSource("a"), settingsSource("b")], 1);

  view.rerender({ rows: [settingsSource("a")] });
  await act(async () => view.result.current.submit());

  expect(view.result.current.gone).toBe(true);
  expect(save).not.toHaveBeenCalled();
});
