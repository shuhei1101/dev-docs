import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test } from "vitest";

import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";
import {
  PROBLEM_HEADERS,
  metadataResponse,
  problem,
  refsResponse,
  settingsSource,
  settingsView,
} from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderApp } from "@tests/helpers/render-app";

const ADDRESS = "http://127.0.0.1:8786";

const useMetadata = (response: () => Response) =>
  server.use(
    http.get("/_api/settings/sources", () => HttpResponse.json(settingsView([settingsSource("sample")]))),
    http.get("/_api/sources/:source/refs", () => HttpResponse.json(refsResponse())),
    http.get("/_api/sources/sample/metadata", response),
  );

beforeEach(() => {
  usePendingEditsStore.setState({ bySource: {}, baseCommitBySource: {} });
});

test("test_metadata_screen", async () => {
  useMetadata(() => HttpResponse.json(metadataResponse()));

  renderApp("/sample/_metadata");

  const tablist = await screen.findByRole("tablist");
  expect(within(tablist).getAllByRole("tab")).toHaveLength(6);
  expect(screen.getByRole("tab", { name: /用語集/, selected: true })).toBeInTheDocument();
  expect(await screen.findByText("配信元")).toBeInTheDocument();
});

test("test_metadata_screen_when_locate", async () => {
  useMetadata(() => HttpResponse.json(metadataResponse()));
  usePendingEditsStore.setState({
    bySource: {
      sample: [
        {
          key: "tags:n1:update",
          kind: "tags",
          op: "update",
          docId: "n1",
          docKind: "note",
          expectedVersion: "v-n1",
          docPath: "notes/n1.yaml",
          values: { tags: ["topic:b"] },
          before: { tags: ["topic:a"] },
          label: "タグ: n1",
        },
      ],
    },
  });

  renderApp("/sample/_metadata?panel=edits");

  await userEvent.click(await screen.findByRole("button", { name: "タグ: n1 の行へ移動" }));

  expect(screen.getByRole("tab", { name: /タグ/, selected: true })).toBeInTheDocument();
  await waitFor(() => expect(document.activeElement?.id).toBe("metadata-row-tags-n1"));
});

test.each([
  ["summary", "fields"],
  ["@file", "file"],
])("test_metadata_screen_when_locate_body(%s)", async (path, mode) => {
  useMetadata(() => HttpResponse.json(metadataResponse()));
  server.use(http.get("/_api/sources/sample/docs/*", () => HttpResponse.json({}, { status: 503 })));
  usePendingEditsStore.setState({
    bySource: {
      sample: [
        {
          key: `body:a:${path}`,
          kind: "body",
          op: "update",
          docId: "a",
          docKind: "rule",
          expectedVersion: "v-a",
          docPath: "docs/rule/a.yaml",
          values: { [path]: "修正後" },
          before: { [path]: "修正前" },
          label: "概要（docs/rule/a.yaml）",
        },
      ],
    },
  });

  const { router } = renderApp("/sample/_metadata?panel=edits");

  await userEvent.click(
    await screen.findByRole("button", { name: "概要（docs/rule/a.yaml） の行へ移動" }),
  );

  await waitFor(() => expect(router.state.location.pathname).toBe("/sample/docs/rule/a.yaml"));
  expect(router.state.location.search).toMatchObject({ edit: mode, panel: "edits" });
});

test("test_metadata_screen_when_not_found", async () => {
  useMetadata(() =>
    HttpResponse.json(problem(404, { title: "UnknownSourceError", missing: "source", value: "sample" }), {
      status: 404,
      headers: PROBLEM_HEADERS,
    }),
  );

  const { router } = renderApp("/sample/_metadata");

  expect(await screen.findByRole("heading", { name: "配信元 sample はありません" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/sample/_metadata");
});

test("test_metadata_screen_when_unreachable", async () => {
  useMetadata(() =>
    HttpResponse.json(
      problem(503, {
        title: "ProjectIndexUnreachableError",
        projectIndex: { address: ADDRESS, reason: "接続を拒否されました", kind: "unreachable" },
      }),
      { status: 503, headers: PROBLEM_HEADERS },
    ),
  );

  renderApp("/sample/_metadata");

  expect(await screen.findByText(ADDRESS)).toBeInTheDocument();
  expect(screen.getByText("接続を拒否されました")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "再読み込み" })).toBeInTheDocument();
});

test("test_metadata_screen_when_pending", async () => {
  const refs: (string | null)[] = [];
  useMetadata(() => HttpResponse.json(metadataResponse()));
  server.use(
    http.get("/_api/sources/sample/metadata", ({ request }) => {
      refs.push(new URL(request.url).searchParams.get("ref"));
      return HttpResponse.json(metadataResponse());
    }),
  );
  usePendingEditsStore.setState({
    bySource: {
      sample: [
        {
          key: "tags:n1:update",
          kind: "tags",
          op: "update",
          docId: "n1",
          docKind: "note",
          expectedVersion: "v-n1",
          docPath: "notes/n1.yaml",
          values: { tags: ["topic:b"] },
          before: { tags: ["topic:a"] },
          label: "タグ: n1",
        },
      ],
    },
    baseCommitBySource: { sample: "aaa1111" },
  });

  renderApp("/sample/_metadata");

  await screen.findByRole("tablist");
  expect(refs[0]).toBe("aaa1111");
});

test("test_metadata_screen_when_not_pending", async () => {
  const refs: (string | null)[] = [];
  useMetadata(() => HttpResponse.json(metadataResponse()));
  server.use(
    http.get("/_api/sources/sample/metadata", ({ request }) => {
      refs.push(new URL(request.url).searchParams.get("ref"));
      return HttpResponse.json(metadataResponse());
    }),
  );

  renderApp("/sample/_metadata");

  await screen.findByRole("tablist");
  expect(refs[0]).toBeNull();
});

const fireBeforeUnload = () => {
  const event = new Event("beforeunload", { cancelable: true });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
};

test("test_metadata_screen_when_query_in_url", async () => {
  useMetadata(() => HttpResponse.json(metadataResponse()));
  const { router } = renderApp("/sample/_metadata?q=%E9%85%8D%E4%BF%A1");
  const input = await screen.findByLabelText("絞り込み");

  expect(input).toHaveValue("配信");
  expect(await screen.findByText("配信元")).toBeInTheDocument();
  const length = window.history.length;
  await userEvent.clear(input);
  await userEvent.type(input, "term");

  await waitFor(() => expect(router.state.location.search).toMatchObject({ q: "term" }));
  expect(window.history.length).toBe(length);
});

test("test_metadata_screen_when_search", async () => {
  useMetadata(() => HttpResponse.json(metadataResponse()));
  renderApp("/sample/_metadata");
  await screen.findByRole("tablist");

  await userEvent.click(screen.getByRole("button", { name: "検索 Ctrl K" }));
  expect(await screen.findByPlaceholderText("文書を検索")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByPlaceholderText("文書を検索")).not.toBeInTheDocument());

  await userEvent.keyboard("{Control>}k{/Control}");
  expect(await screen.findByPlaceholderText("文書を検索")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByPlaceholderText("文書を検索")).not.toBeInTheDocument());

  await userEvent.keyboard("?");
  expect(await screen.findByRole("heading", { name: "キーボードのショートカット" })).toBeInTheDocument();
});

test("test_metadata_screen_when_leave_guard", async () => {
  useMetadata(() => HttpResponse.json(metadataResponse()));
  renderApp("/sample/_metadata");
  await screen.findByText("配信元");

  expect(fireBeforeUnload().defaultPrevented).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: /を削除$/ }));

  expect(fireBeforeUnload().defaultPrevented).toBe(true);
});
