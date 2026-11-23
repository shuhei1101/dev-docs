import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";

import { PendingPanel } from "@/features/metadata/metadata/pending-panel";
import { type PendingEdit, usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
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

const renderPanel = () =>
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <PendingPanel source="sample" branch="develop" open onOpenChange={() => {}} onLocate={() => {}} />
    </QueryClientProvider>,
  );

beforeEach(() => {
  usePendingEditsStore.setState({
    bySource: { sample: [edit("n1"), edit("n2")] },
    baseCommitBySource: { sample: "aaa1111" },
  });
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

const BRANCH = "project-index/conflict/20261123-103000-aaa1111";

const conflicted = (script: Record<string, unknown> | null) => ({
  applied: false,
  results: [],
  commit: null,
  conflict: {
    branch: BRANCH,
    baseCommit: "aaa1111aaa1111aaa1111aaa1111aaa1111aaa1",
    reasons: [{ key: "tags:n1:update", reason: "tags が変わっています" }],
    script,
  },
});

const commitWith = async (message = "タグを修正する") => {
  await userEvent.click(screen.getByRole("button", { name: "コミット" }));
  const dialog = await screen.findByRole("dialog", { name: "コミットしますか？" });
  await userEvent.type(within(dialog).getByRole("textbox", { name: "コミットの説明" }), message);
  await userEvent.click(within(dialog).getByRole("button", { name: "コミット" }));
};

test("test_pending_panel_when_conflict", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(conflicted({ exitCode: 0, timedOut: false, prUrl: "https://github.com/o/r/pull/9", stderr: "" })),
    ),
  );
  renderPanel();

  await commitWith();

  expect(await screen.findByText("ほかの変更と衝突したため、修正をブランチに残しました")).toBeInTheDocument();
  expect(screen.getByText(new RegExp(BRANCH))).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "PR を開く" })).toHaveAttribute("href", "https://github.com/o/r/pull/9");
  expect(screen.getByText("タグ: n1")).toBeInTheDocument();
  expect(screen.getByText("タグ: n2")).toBeInTheDocument();
  expect(screen.getByText("tags が変わっています")).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample ?? []).toHaveLength(0);
});

test("test_pending_panel_when_conflict_script_failed", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(conflicted({ exitCode: 1, timedOut: false, prUrl: null, stderr: "authentication required" })),
    ),
  );
  renderPanel();

  await commitWith();

  expect(await screen.findByText("衝突したときのスクリプトが失敗しました（終了コード 1）。")).toBeInTheDocument();
  expect(screen.getByText("authentication required")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "PR を開く" })).toBeNull();
});

test("test_pending_panel_when_conflict_script_not_configured", async () => {
  server.use(http.post("/_api/sources/sample/commits", () => HttpResponse.json(conflicted(null))));
  renderPanel();

  await commitWith();

  expect(await screen.findByText(/衝突したときのスクリプトが登録されていないため、PR は作成していません。/)).toBeInTheDocument();
});

test("test_pending_panel_when_dry_run_conflict", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json({ ...conflicted(null), conflict: { ...conflicted(null).conflict, branch: null } }),
    ),
  );
  renderPanel();

  await userEvent.click(screen.getByRole("button", { name: "差分確認" }));

  expect(await screen.findByText("コミットすると、ほかの変更と衝突して修正がブランチに残ります")).toBeInTheDocument();
  expect(screen.getByText("tags が変わっています")).toBeInTheDocument();
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
});

test("test_pending_panel_when_base_commit_unusable", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(problem(409, { title: "BaseCommitUnusableError", detail: "not_ancestor" }), {
        status: 409,
        headers: PROBLEM_HEADERS,
      }),
    ),
    http.get("/_api/sources/sample/metadata", () => {
      const latest = metadataResponse();
      return HttpResponse.json({
        ...latest,
        baseCommit: "ccc3333",
        kinds: latest.kinds.map((kind) =>
          kind.id === "tags"
            ? { ...kind, rows: [{ ...(kind.rows[0] as object), id: "n1", values: { tags: ["topic:a"] } }, { ...(kind.rows[0] as object), id: "n2", values: { tags: ["topic:a"] } }] }
            : kind,
        ),
      });
    }),
  );
  renderPanel();

  await commitWith();
  const restart = await screen.findByRole("button", { name: "最新の内容で続ける" });
  await userEvent.click(restart);

  await waitFor(() => expect(usePendingEditsStore.getState().baseCommitBySource.sample).toBe("ccc3333"));
  expect(screen.queryByText("BaseCommitUnusableError")).toBeNull();
  expect(usePendingEditsStore.getState().bySource.sample).toHaveLength(2);
});

test("test_pending_panel_when_restart_dropped", async () => {
  server.use(
    http.post("/_api/sources/sample/commits", () =>
      HttpResponse.json(problem(409, { title: "BaseCommitUnusableError", detail: "not_ancestor" }), {
        status: 409,
        headers: PROBLEM_HEADERS,
      }),
    ),
    http.get("/_api/sources/sample/metadata", () => {
      const latest = metadataResponse();
      return HttpResponse.json({
        ...latest,
        baseCommit: "ccc3333",
        kinds: latest.kinds.map((kind) =>
          kind.id === "tags"
            ? { ...kind, rows: [{ ...(kind.rows[0] as object), id: "n1", values: { tags: ["topic:x"] } }, { ...(kind.rows[0] as object), id: "n2", values: { tags: ["topic:a"] } }] }
            : kind,
        ),
      });
    }),
  );
  renderPanel();

  await commitWith();
  await userEvent.click(await screen.findByRole("button", { name: "最新の内容で続ける" }));

  expect(await screen.findByText("最新の内容と食い違うため、次の変更を取り消しました")).toBeInTheDocument();
  expect(screen.getByText("タグ: n1")).toBeInTheDocument();
  expect((usePendingEditsStore.getState().bySource.sample ?? []).map((item) => item.key)).toEqual(["tags:n2:update"]);
});
