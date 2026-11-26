import { renderHook } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";

import {
  WHOLE_FILE,
  bodyEditKey,
  previewQueryOptions,
  upsertBodyEdit,
  usePendingBodyMode,
} from "@/features/docs/doc-view/edit";
import type { DocumentEdit } from "@/shared/api/generated/model";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import { docEdit } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { HttpResponse, http } from "msw";

const edit = docEdit() as unknown as DocumentEdit;

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

test("test_body_edit_key", () => {
  expect(bodyEditKey(edit, "summary")).toBe("body:n1:summary");
});

test("test_upsert_body_edit", () => {
  upsertBodyEdit("s", edit, {
    path: "summary",
    label: "概要",
    before: "A",
    value: "B",
  });
  const afterFirst = usePendingEditsStore.getState().bySource.s ?? [];
  const baseCommit = usePendingEditsStore.getState().baseCommitBySource.s;
  upsertBodyEdit("s", edit, {
    path: "summary",
    label: "概要",
    before: "A",
    value: "A",
  });

  expect(afterFirst).toEqual([
    {
      key: "body:n1:summary",
      kind: "body",
      op: "update",
      docId: "n1",
      docKind: "note",
      expectedVersion: "v-n1",
      docPath: "notes/n1.yaml",
      values: { summary: "B" },
      before: { summary: "A" },
      label: "概要（notes/n1.yaml）",
    },
  ]);
  expect(baseCommit).toBe("ccc3333");
  expect(usePendingEditsStore.getState().bySource.s ?? []).toHaveLength(0);
});

test("test_use_pending_body_mode", () => {
  const other = docEdit({
    docId: "n2",
    filePath: "notes/n2.yaml",
  }) as unknown as DocumentEdit;
  upsertBodyEdit("s", edit, {
    path: "summary",
    label: "概要",
    before: "A",
    value: "B",
  });
  upsertBodyEdit("s", other, {
    path: WHOLE_FILE,
    label: "ファイル全体",
    before: "x",
    value: "y",
  });

  const { result } = renderHook(() => usePendingBodyMode("s", edit));

  expect(result.current).toEqual({ fields: true, file: false });
});

test("test_preview_query_options", async () => {
  const bodies: unknown[] = [];
  server.use(
    http.post("/_api/sources/s/preview", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({
        markdown: "# n1",
        conversionError: null,
        fallback: false,
      });
    }),
  );
  const options = previewQueryOptions("s", "notes/n1", "title: n1\n");

  const result = await (
    options.queryFn as (context: { signal: AbortSignal }) => Promise<unknown>
  )({
    signal: new AbortController().signal,
  });

  expect(bodies).toEqual([{ path: "notes/n1", content: "title: n1\n" }]);
  expect(result).toEqual({
    markdown: "# n1",
    conversionError: null,
    fallback: false,
  });
  expect(options.queryKey).toEqual([
    "view",
    "preview",
    "s",
    "notes/n1",
    "title: n1\n",
  ]);
});
