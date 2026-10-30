import { screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";
import { refsResponse, settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderInRouter } from "@tests/helpers/render";

const useHandlers = (refs = vi.fn(() => HttpResponse.json(refsResponse()))) => {
  server.use(
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView([settingsSource("s"), settingsSource("t")])),
    ),
    http.get("/_api/sources/:source/refs", refs),
  );
  return refs;
};

test("test_not_found_screen", async () => {
  useHandlers();

  const { router } = renderInRouter(
    <NotFoundScreen
      data={{ missing: { kind: "doc", source: "s", ref: "main", path: "a.md" } }}
    />,
    "/s/a.md",
  );

  expect(await screen.findByRole("heading", { name: "文書が見つかりません" })).toBeInTheDocument();
  expect(screen.getByText("a.md")).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "s のトップを開く" })).toBeInTheDocument();
  const list = await screen.findByRole("list", { name: "配信中の配信元" });
  expect(list.querySelectorAll("a")).toHaveLength(2);
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_not_found_screen_when_source_missing", async () => {
  const refs = useHandlers();

  renderInRouter(
    <NotFoundScreen data={{ missing: { kind: "source", source: "zzz" } }} />,
    "/zzz/a.md",
  );

  expect(await screen.findByRole("heading", { name: "配信元 zzz はありません" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("list", { name: "配信中の配信元" })).toBeInTheDocument());
  expect(refs).not.toHaveBeenCalled();
});
