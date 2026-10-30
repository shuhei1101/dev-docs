import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { toast } from "sonner";
import { expect, test, vi } from "vitest";

import { SourceDeleteDialog } from "@/features/settings/settings/components/source-delete-dialog";
import { settingsSource } from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const sources = [settingsSource("a"), settingsSource("b")];

const renderDialog = (onOpenChange = vi.fn()) => {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <SourceDeleteDialog
        open
        onOpenChange={onOpenChange}
        sources={sources as never}
        index={0}
      />
    </QueryClientProvider>,
  );
  return onOpenChange;
};

test("test_source_delete_dialog", async () => {
  let body = null as { sources: { id: string }[] } | null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({
        sources: [{ id: "b", status: "serving", errors: [] }],
      });
    }),
  );
  const onOpenChange = renderDialog();

  await userEvent.click(screen.getByRole("button", { name: "削除" }));

  await waitFor(() =>
    expect(body?.sources.map((item) => item.id)).toEqual(["b"]),
  );
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
});

test("test_source_delete_dialog_when_failed", async () => {
  server.use(
    http.put("/_api/settings/sources", () =>
      HttpResponse.json(
        {
          type: "urn:dev-docs:error:Error",
          title: "Error",
          status: 500,
          detail: "x",
          nextSteps: [],
        },
        {
          status: 500,
          headers: { "Content-Type": "application/problem+json" },
        },
      ),
    ),
  );
  const onOpenChange = renderDialog();

  await userEvent.click(screen.getByRole("button", { name: "削除" }));

  await waitFor(() =>
    expect(toast.error).toHaveBeenCalledWith(
      "端末の設定を保存できませんでした。",
    ),
  );
  expect(onOpenChange).not.toHaveBeenCalledWith(false);
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});
