import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { SourceEditDialog } from "@/features/settings/settings/components/source-edit-dialog";
import {
  PROBLEM_HEADERS,
  problem,
  settingsSource,
} from "@tests/helpers/fixtures";
import { server } from "@tests/helpers/msw-server";
import { createTestQueryClient } from "@tests/helpers/render";

const sources = [settingsSource("a")];

const renderDialog = (index: number | null, onOpenChange = vi.fn()) => {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <SourceEditDialog
        open
        onOpenChange={onOpenChange}
        sources={sources as never}
        index={index}
      />
    </QueryClientProvider>,
  );
  return onOpenChange;
};

test("test_source_edit_dialog", async () => {
  let body: { sources: { id: string }[] } | null = null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({
        sources: [{ id: "extra", status: "serving", errors: [] }],
      });
    }),
  );
  const onOpenChange = renderDialog(null);

  await userEvent.type(screen.getByLabelText(/配信元の ID/), "extra");
  await userEvent.type(
    screen.getByLabelText(/設定ファイル/),
    "/x/dev-docs.yaml",
  );
  await userEvent.type(screen.getByLabelText(/読み取りの範囲/), "/x/**");
  await userEvent.click(screen.getByRole("button", { name: "追加" }));

  await waitFor(() => expect(body?.sources.at(-1)?.id).toBe("extra"));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
});

test("test_source_edit_dialog_when_edit", () => {
  renderDialog(0);

  expect(screen.queryByLabelText(/配信元の ID/)).toBeNull();
  expect(screen.getByText("配信元 a")).toBeInTheDocument();
});

test("test_source_edit_dialog_when_invalid", async () => {
  const save = vi.fn(() => HttpResponse.json({ sources: [] }));
  server.use(http.put("/_api/settings/sources", save));
  renderDialog(null);

  await userEvent.click(screen.getByRole("button", { name: "追加" }));

  expect(
    await screen.findByText("配信元の ID を入力してください。"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("設定ファイルを 1 つ以上入力してください。"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("読み取りの範囲を 1 つ以上入力してください。"),
  ).toBeInTheDocument();
  expect(save).not.toHaveBeenCalled();
});

test("test_source_edit_dialog_when_outside_read", async () => {
  let body: { sources: Record<string, unknown>[] } | null = null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({
        sources: [{ id: "a", status: "serving", errors: [] }],
      });
    }),
  );
  renderDialog(0);
  const toggle = screen.getByRole("switch", {
    name: "範囲の外から参照できるようにする",
  });

  expect(toggle).toBeChecked();
  await userEvent.click(toggle);
  await userEvent.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() =>
    expect(body?.sources[0]).toMatchObject({ id: "a", outside_read: false }),
  );
});

test("test_source_edit_dialog_when_conflict", async () => {
  server.use(
    http.put("/_api/settings/sources", () =>
      HttpResponse.json(problem(409, { current: "v2" }), {
        status: 409,
        headers: PROBLEM_HEADERS,
      }),
    ),
  );
  const onOpenChange = renderDialog(0);

  await userEvent.click(screen.getByRole("button", { name: "保存" }));

  expect(
    await screen.findByText("他の変更があったため保存できませんでした"),
  ).toBeInTheDocument();
  expect(onOpenChange).not.toHaveBeenCalledWith(false);
  expect(screen.getByLabelText(/設定ファイル/)).toHaveValue(
    "/home/me/a/dev-docs.yaml",
  );
});

test("test_source_edit_dialog_when_storage", async () => {
  let body: { sources: Record<string, unknown>[] } | null = null;
  server.use(
    http.put("/_api/settings/sources", async ({ request }) => {
      body = (await request.json()) as typeof body;
      return HttpResponse.json({
        sources: [{ id: "a", status: "serving", errors: [] }],
      });
    }),
  );
  renderDialog(0);
  const storage = screen.getByRole("combobox", { name: /読み書きの方法/ });

  expect(storage).toHaveTextContent("自動");
  await userEvent.click(storage);
  await userEvent.click(
    await screen.findByRole("option", { name: "ディスク" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() =>
    expect(body?.sources[0]).toMatchObject({
      id: "a",
      storage: { type: "disk" },
    }),
  );
});

test("test_storage_field", async () => {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <SourceEditDialog
        open
        onOpenChange={vi.fn()}
        sources={
          [{ ...settingsSource("local"), storage: { type: "disk" } }] as never
        }
        index={0}
      />
    </QueryClientProvider>,
  );
  const storage = screen.getByRole("combobox", { name: /読み書きの方法/ });

  expect(storage).toHaveTextContent("ディスク");
  expect(
    screen.getByText(
      "Git はコミットから読み、ディスクはフォルダのファイルをそのまま読みます。保存済みの読み書きの方法は自動に戻せません。",
    ),
  ).toBeInTheDocument();
  await userEvent.click(storage);
  expect(
    await screen.findByRole("option", { name: "Git" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "自動" })).toBeNull();
});

test("test_storage_field_when_not_stored", async () => {
  renderDialog(null);
  const storage = screen.getByRole("combobox", { name: /読み書きの方法/ });

  expect(
    screen.getByText(
      "自動は、フォルダが Git の作業ツリーの中なら Git、外ならディスクで読み書きします。コミットしないフォルダはディスクを選択します。",
    ),
  ).toBeInTheDocument();
  await userEvent.click(storage);
  expect(
    await screen.findByRole("option", { name: "自動" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Git" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "ディスク" })).toBeInTheDocument();
});
