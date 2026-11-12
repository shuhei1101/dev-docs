import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useSettingsPutSettingsSources } from "@/shared/api/generated/settings/settings";
import type { SourceEntry } from "@/shared/api/generated/model";

/** 端末の設定の保存。成功後に全ての問い合わせを再取得し、通知を出す */
export const useSaveSources = () => {
  const queryClient = useQueryClient();
  const mutation = useSettingsPutSettingsSources({
    mutation: {
      // 失敗は呼び出し元が扱う（422 はダイアログが項目に出し、他は handleAppError）
      meta: { handleError: false },
      onSuccess: async () => {
        await queryClient.invalidateQueries({ refetchType: "all" });
        toast.success("端末の設定を保存し、配信元を再読み込みしました。");
      },
    },
  });
  return {
    ...mutation,
    mutateAsync: (sources: SourceEntry[]) =>
      mutation.mutateAsync({ data: { sources } }),
  };
};
