import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";
import {
  refsResponse,
  settingsSource,
  settingsView,
} from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderInRouter } from "@tests/helpers/render";

const useHandlers = (refs = vi.fn(() => HttpResponse.json(refsResponse()))) => {
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(
        settingsView([settingsSource("s"), settingsSource("t")]),
      ),
    ),
    http.get("/_api/sources/:source/refs", refs),
  );
  return refs;
};

test("test_not_found_screen", async () => {
  useHandlers();

  const { router } = renderInRouter(
    <NotFoundScreen data={{ missing: "doc", value: "a.md" }} />,
    "/s/a.md",
  );

  expect(
    await screen.findByRole("heading", { name: "文書が見つかりません" }),
  ).toBeInTheDocument();
  expect(screen.getByText("a.md")).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: "s のトップを開く" }),
  ).toBeInTheDocument();
  await userEvent.click(
    await screen.findByRole("button", { name: "配信元を切り替える" }),
  );
  expect(await screen.findAllByRole("menuitem")).toHaveLength(2);
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_not_found_screen_when_source_missing", async () => {
  const refs = useHandlers();

  renderInRouter(
    <NotFoundScreen data={{ missing: "source", value: "unknown" }} />,
    "/unknown/a.md",
  );

  expect(
    await screen.findByRole("heading", { name: "配信元 unknown はありません" }),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByRole("list", { name: "配信中の配信元" }),
    ).toBeInTheDocument(),
  );
  expect(refs).not.toHaveBeenCalled();
});
