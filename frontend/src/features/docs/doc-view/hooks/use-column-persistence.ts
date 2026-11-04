import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { MdmarkColumnsChangeHandler } from "@/features/docs/doc-view/hooks/use-mdmark";
import { viewPutColumns } from "@/shared/api/generated/view/view";

type Params = {
  /** 配信元の ID */
  source: string;
  /** `+columns` の表のキーを出る順に並べたもの */
  columnKeys: string[];
};

/** mdmark の `onColumnsChange` に渡す関数を返し、受けた表の隠す列を保存する。失敗しても表は切り替えたままにする */
export const useColumnPersistence = ({
  source,
  columnKeys,
}: Params): MdmarkColumnsChangeHandler => {
  const queryClient = useQueryClient();
  return ({ tableIndex, hidden }) => {
    const table = columnKeys[tableIndex];
    if (table === undefined) return;
    viewPutColumns(source, { table, hidden })
      .then(() =>
        queryClient.invalidateQueries({
          queryKey: ["view", "document", source],
        }),
      )
      .catch(() => toast.error("列の表示を保存できませんでした。"));
  };
};
