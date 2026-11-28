import { useBlocker } from "@tanstack/react-router";

import { type ConfirmRequest, useConfirmDialog } from "@/app/confirm-dialog";

type Options = {
  /** 画面の中の移動も止めるときの確認のダイアログの文面。省くとタブを閉じる・再読み込みだけ警告する */
  navigation?: ConfirmRequest;
};

/** `active` の間はタブを閉じる・再読み込みを警告し、`navigation` があれば画面の中の移動も確認のダイアログで止める */
export const useLeaveGuard = (
  active: boolean,
  { navigation }: Options = {},
): void => {
  const confirm = useConfirmDialog();
  useBlocker({
    enableBeforeUnload: () => active,
    shouldBlockFn: async () => {
      if (!active || navigation === undefined) return false;
      return !(await confirm(navigation));
    },
  });
};
