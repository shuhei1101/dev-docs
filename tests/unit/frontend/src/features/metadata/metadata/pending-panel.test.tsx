import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";

import { PendingPanel } from "@/features/metadata/metadata/pending-panel";
import { type PendingEdit, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
import { PROBLEM_HEADERS, problem } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const edit = (docId: string): PendingEdit => ({
  key: `tags:${docId}:update`,
  kind: "tags",
  op: "update",
  docId,
  docKind: "note",
  expectedVersion: `v-${docId}`,
  values: { tags: ["topic:b"] },
  before: { tags: ["topic:a"] },
  label: `タグ: ${docId}`,
});

const renderPanel = () =>
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <PendingPanel source="sample" branch="develop" open onOpenChange={() => {}} onLocate={() => {}} />
    </QueryClientProvider>,
  );

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: { sample: [edit("n1"), edit("n2")] } });
});

test("test_pending_panel_when_dry_run", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json({
        applied: false,
        results: [
          { key: "tags:n1:update", status: "updated", version: "v2", diff: "+   - topic:b n1" },
          { key: "tags:n2:update", status: "updated", version: "v3", diff: "+   - topic:b n2" },
        ],
        commit: null,
      }),
    ),
  );
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "差分確認" }));

  expect(await screen.findByText(/topic:b n1/)).toBeInTheDocument();
  expect(screen.getByText(/topic:b n2/)).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
});

test("test_pending_panel_when_rejected", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(
        problem(422, {
          title: "検査に合格しませんでした",
          errors: [{ key: "tags:n2:update", path: "tags", reason: "使用できないタグです" }],
        }),
        { status: 422, headers: PROBLEM_HEADERS },
      ),
    ),
  );
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "コミット" }));
  const dialog = await screen.findByRole("dialog", { name: "コミットしますか？" });
  await userEvent.type(within(dialog).getByRole("textbox", { name: "コミットの説明" }), "タグを修正する");
  await userEvent.click(within(dialog).getByRole("button", { name: "コミット" }));

  expect(await screen.findByText("tags: 使用できないタグです")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "再試行" })).toBeInTheDocument();
  expect(screen.getByText(/編集中の変更はそのままです。/)).toBeInTheDocument();
});

test("test_pending_panel_when_message_empty", async () => {
  const post = vi.fn(() => HttpResponse.json({ applied: true, results: [], commit: null }));
  server.use(http.post("/_api/sources/sample/commits", post));
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "コミット" }));
  const dialog = await screen.findByRole("dialog", { name: "コミットしますか？" });
  const confirm = within(dialog).getByRole("button", { name: "コミット" });
  await userEvent.click(confirm);

  expect(confirm).toBeDisabled();
  expect(post).not.toHaveBeenCalled();
});
