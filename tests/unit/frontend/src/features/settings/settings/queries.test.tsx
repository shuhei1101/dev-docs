import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { toast } from "sonner";
import { expect, test, vi } from "vitest";
import type { ReactNode } from "react";

import { useSaveSources } from "@/features/settings/settings/queries";
import { settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

test("test_use_save_sources", async () => {
  const queryClient = createTestQueryClient();
  const get = vi.fn(() => HttpResponse.json(settingsView([settingsSource("a")])));
  server.use(
    http.get("/_api/settings/sources", get),
    http.put("/_api/settings/sources", () =>
      HttpResponse.json({ sources: [{ id: "a", status: "serving", errors: [] }] }),
    ),
  );
  await queryClient.fetchQuery({
    queryKey: ["settings"],
    queryFn: () => fetch("/_api/settings/sources").then((response) => response.json()),
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useSaveSources(), { wrapper });

  await result.current.mutateAsync([{ id: "a", config: ["/a/dev-docs.yaml"], enabled: true }] as never);

  await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  expect(toast.success).toHaveBeenCalledTimes(1);
  expect(toast.success).toHaveBeenCalledWith("端末の設定を保存し、配信元を再読み込みしました。");
});

test("test_use_save_sources_when_expected_version", async () => {
  const bodies: unknown[] = [];
  server.use(
    http.get("/_api/settings/sources", () => HttpResponse.json(settingsView([settingsSource("a")]))),
    http.put("/_api/settings/sources", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ sources: [{ id: "a", status: "serving", errors: [] }] });
    }),
  );
  const queryClient = createTestQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useSaveSources(), { wrapper });
  const sources = [{ id: "a", config: ["/a/dev-docs.yaml"] }] as never;

  await result.current.mutateAsync(sources, "v1");
  await result.current.mutateAsync(sources, undefined);

  expect(bodies[0]).toMatchObject({ expectedVersion: "v1" });
  expect(bodies[1]).not.toHaveProperty("expectedVersion");
});
