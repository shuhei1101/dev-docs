import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { ConfirmDialogProvider, useConfirmDialog } from "@/app/confirm-dialog";

let result: boolean | null = null;

const Opener = () => {
  const confirm = useConfirmDialog();
  return (
    <button
      type="button"
      onClick={async () => {
        result = await confirm({
          title: "削除しますか?",
          description: "取り消せません",
          confirmLabel: "削除",
          destructive: true,
        });
      }}
    >
      開く
    </button>
  );
};

const open = async () => {
  result = null;
  render(
    <ConfirmDialogProvider>
      <Opener />
    </ConfirmDialogProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "開く" }));
  await screen.findByRole("alertdialog");
};

test("test_use_confirm_dialog", async () => {
  await open();

  await userEvent.click(screen.getByRole("button", { name: "削除" }));

  await waitFor(() => expect(result).toBe(true));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
});

test("test_use_confirm_dialog_when_cancel", async () => {
  await open();

  await userEvent.keyboard("{Escape}");

  await waitFor(() => expect(result).toBe(false));
});
