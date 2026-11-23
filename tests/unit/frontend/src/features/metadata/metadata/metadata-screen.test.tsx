import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test } from "vitest";

import { usePendingEditsStore } from "@/features/metadata/shared/pending-edits-store";
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
  usePendingEditsStore.setState({ bySource: {} });
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
