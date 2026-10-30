import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test, vi } from "vitest";

import { documentResponse, group, page, refsResponse, settingsSource, settingsView } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { renderApp } from "@tests/helpers/render-app";

const mount = vi.hoisted(() => vi.fn());

vi.mock("https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.js", () => ({ mount }));

const useHandlers = (document: Record<string, unknown>) =>
  server.use(
    http.get("/_api/sources/:source/docs/*", () => HttpResponse.json(document)),
    http.get("/_api/sources/:source/docs", () => HttpResponse.json(document)),
    http.get("/_api/sources/:source/refs", () => HttpResponse.json(refsResponse())),
    http.get("/_api/settings/sources", () =>
      HttpResponse.json(settingsView([settingsSource("s")])),
    ),
  );

beforeEach(() => {
  mount.mockReset();
  mount.mockReturnValue({ update: vi.fn(), destroy: vi.fn() });
});

test("test_doc_view_screen", async () => {
  useHandlers(documentResponse());

  renderApp("/s/a.md");

  expect(await screen.findByRole("heading", { level: 1, name: "A" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "パンくず" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "A" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(document.title).toBe("A | s | dev-docs"));
  await waitFor(() => expect(mount).toHaveBeenCalled());
  expect((mount.mock.calls[0][1] as { markdown: string }).markdown).not.toContain("# A");
});

test("test_doc_view_screen_when_empty_tab", async () => {
  useHandlers(documentResponse());
  const { router } = renderApp("/s/a.md");
  await screen.findByRole("heading", { level: 1, name: "A" });

  await userEvent.click(screen.getByText("規約"));

  expect(await screen.findByText("規約の文書はありません")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/s/a.md");
});

test("test_doc_view_screen_when_conversion_error", async () => {
  useHandlers(
    documentResponse({
      markdown: null,
      conversionError: { reason: "timeout", kind: "rules", script: "scripts/convert.py", detail: "x" },
      tabs: [{ title: "設計書", active: true, items: [group("設計", [page("A", "a.md")])] }],
    }),
  );

  renderApp("/s/a.md");

  expect(await screen.findByText("本文を変換できませんでした")).toBeInTheDocument();
  expect(mount).not.toHaveBeenCalled();
});
