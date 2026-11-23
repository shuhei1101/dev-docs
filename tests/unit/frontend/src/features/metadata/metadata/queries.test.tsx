import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import type { ReactNode } from "react";

import { useCommitEdits, useRestartFromLatest } from "@/features/metadata/metadata/queries";
import { type PendingEdit, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import { AppError } from "@/shared/core/app-error";
import { PROBLEM_HEADERS, metadataResponse, problem } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const edit = (docId: string): PendingEdit => ({
  key: `tags:${docId}:update`,
  kind: "tags",
  op: "update",
  docId,
  docKind: "note",
  expectedVersion: `v-${docId}`,
  docPath: `notes/${docId}.yaml`,
  values: { tags: ["topic:b"] },
  before: { tags: ["topic:a"] },
  label: `タグ: ${docId}`,
});

const committed = (applied: boolean) => ({
  applied,
  results: [
    { key: "tags:n1:update", status: "updated", version: "v2", diff: "d1" },
    { key: "tags:n2:update", status: "updated", version: "v3", diff: "d2" },
  ],
  commit: applied ? { sha: "0a1b2c3", branch: "develop" } : null,
});

const renderCommit = () => {
  const queryClient = createTestQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return renderHook(() => useCommitEdits("sample"), { wrapper });
};

beforeEach(() => {
  usePendingEditsStore.setState({
    bySource: { sample: [edit("n1"), edit("n2")] },
    baseCommitBySource: { sample: "aaa1111" },
  });
});

test("test_use_commit_edits", async () => {
  const get = vi.fn(() => HttpResponse.json(metadataResponse()));
  server.use(
    http.get("/_api/sources/sample/metadata", get),
    http.post("/_api/sources/sample/commits", () => HttpResponse.json(committed(true))),
  );
  const queryClient = createTestQueryClient();
  await queryClient.fetchQuery({
    queryKey: ["/_api/sources/sample/metadata"],
    queryFn: () => fetch("/_api/sources/sample/metadata").then((response) => response.json()),
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useCommitEdits("sample"), { wrapper });

  await result.current.mutateAsync({ dryRun: false, message: "タグを修正する" });

  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
  await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
});

test("test_use_commit_edits_when_dry_run", async () => {
  server.use(http.post("/_api/sources/sample/commits", () => HttpResponse.json(committed(false))));
  const { result } = renderCommit();

  await result.current.mutateAsync({ dryRun: true });

  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
});

test("test_use_commit_edits_when_rejected", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(
        problem(422, { title: "EditsRejectedError", errors: [{ key: "tags:n2:update", path: "tags", reason: "違反" }] }),
        { status: 422, headers: PROBLEM_HEADERS },
      ),
    ),
  );
  const { result } = renderCommit();

  await expect(result.current.mutateAsync({ dryRun: false, message: "m" })).rejects.toBeInstanceOf(AppError);

  await waitFor(() => expect(result.current.error).toBeInstanceOf(AppError));
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
});

test("test_use_commit_edits_when_conflict", async () => {
  const conflict = {
    branch: "project-index/conflict/20261123-103000-aaa1111",
    baseCommit: "aaa1111",
    reasons: [{ key: "tags:n1:update", reason: "tags が変わっています" }],
    script: { exitCode: 0, timedOut: false, prUrl: "https://github.com/o/r/pull/9", stderr: "" },
  };
  const sent: unknown[] = [];
  server.use(
    http.post("/_api/sources/sample/commits", async ({ request }) => {
      sent.push(await request.json());
      return HttpResponse.json({ applied: false, results: [], commit: null, conflict });
    }),
  );
  const { result } = renderCommit();

  const response = await result.current.mutateAsync({ dryRun: false, message: "m" });

  expect(sent[0]).toMatchObject({ baseCommit: "aaa1111" });
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
  expect(response.conflict).toEqual(conflict);
});

test("test_use_restart_from_latest", async () => {
  const urls: string[] = [];
  server.use(
    http.get("/_api/sources/sample/metadata", ({ request }) => {
      urls.push(request.url);
      const latest = metadataResponse();
      return HttpResponse.json({
        ...latest,
        baseCommit: "ccc3333",
        kinds: latest.kinds.map((kind) =>
          kind.id === "tags"
            ? { ...kind, rows: [{ ...kind.rows[0], id: "n1", values: { tags: ["topic:a"] } }, { ...kind.rows[0], id: "n2", values: { tags: ["topic:a"] } }] }
            : kind,
        ),
      });
    }),
  );
  const queryClient = createTestQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useRestartFromLatest("sample"), { wrapper });

  await result.current.mutateAsync();

  expect(new URL(urls[0] ?? "", "http://localhost").searchParams.has("ref")).toBe(false);
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
  expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBe("ccc3333");
});
