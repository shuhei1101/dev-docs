import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test } from "vitest";

import { settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderApp } from "@tests/helpers/render-app";
import { usePreferencesStore } from "@/shared/stores/preferences";

const useSources = (sources: ReturnType<typeof settingsSource>[]) =>
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView(sources)),
    ),
  );

beforeEach(() => {
  usePreferencesStore.setState({ singleKeyShortcuts: true });
});

test("test_settings_screen", async () => {
  useSources([
    settingsSource("a"),
    settingsSource("b", { status: "disabled", enabled: false }),
  ]);

  renderApp("/_settings");

  const table = await screen.findByRole("table", { name: "配信元の表" });
  expect(table.querySelectorAll("tbody tr")).toHaveLength(2);
  expect(
    screen.getByRole("button", { name: "配信元を追加" }),
  ).toBeInTheDocument();
});

test("test_settings_screen_when_empty", async () => {
  useSources([]);

  renderApp("/_settings");

  expect(await screen.findByText("配信元はありません。")).toBeInTheDocument();
  expect(screen.queryByRole("table")).toBeNull();
});

test("test_settings_screen_when_single_key_off", async () => {
  useSources([settingsSource("a")]);
  renderApp("/_settings");
  await screen.findByRole("table", { name: "配信元の表" });

  await userEvent.click(
    screen.getByRole("switch", { name: "1 文字のショートカットを使用する" }),
  );
  await userEvent.keyboard("?");

  expect(screen.queryByRole("dialog")).toBeNull();
});

test("test_settings_screen_when_project_index_failed", async () => {
  const cases = [
    {
      status: 502,
      kind: "failed",
      title: "project-index が要求を処理できませんでした",
    },
    {
      status: 503,
      kind: "timeout",
      title: "project-index から応答がありませんでした",
    },
  ];
  for (const { status, kind, title } of cases) {
    server.use(
      http.get("/_api/settings/sources", () =>
        HttpResponse.json(
          {
            type: "about:blank",
            title: "ProjectIndexError",
            status,
            detail: title,
            nextSteps: [],
            projectIndex: {
              address: "http://127.0.0.1:8786",
              reason: "x",
              kind,
            },
          },
          { status, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );

    const { unmount } = renderApp("/_settings");

    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(screen.queryByText(/project-index を起動してから/)).toBeNull();
    unmount();
  }
});
