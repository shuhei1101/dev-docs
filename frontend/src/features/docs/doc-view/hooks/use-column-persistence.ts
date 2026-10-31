import { useQueryClient } from "@tanstack/react-query";
import { type RefObject, useEffect } from "react";
import { toast } from "sonner";

import { viewPutColumns } from "@/shared/api/generated/view/view";

const MENU = ".mdmark-columns-menu";

/** 列の表示のメニューで出し入れした列を、その表の隠す列として保存する。失敗しても表は切り替えたままにする */
export const useColumnPersistence = (
  ref: RefObject<HTMLElement | null>,
  source: string,
  tableKeys: string[],
): void => {
  const queryClient = useQueryClient();
  useEffect(() => {
    const element = ref.current;
    if (element === null) return;
    const onChange = (event: Event) => {
      const target = event.target as HTMLElement;
      const menu = target.closest(MENU);
      if (menu === null) return;
      const table =
        tableKeys[Array.from(element.querySelectorAll(MENU)).indexOf(menu)];
      if (table === undefined) return;
      const hidden = Array.from(
        menu.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'),
      )
        .filter((input) => !input.checked)
        .map((input) => input.closest("label")?.textContent?.trim() ?? "");
      viewPutColumns(source, { table, hidden })
        .then(() =>
          queryClient.invalidateQueries({
            queryKey: ["view", "document", source],
          }),
        )
        .catch(() => toast.error("列の表示を保存できませんでした。"));
    };
    element.addEventListener("change", onChange);
    return () => element.removeEventListener("change", onChange);
  }, [ref, source, tableKeys, queryClient]);
};
