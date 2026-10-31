import type { SettingsSourcesView } from "@/shared/api/generated/model";

export type ServingSource = { id: string; writable: boolean };

/** 端末の設定の取得から、配信中の配信元（トップバーのメニューの項目）を取り出す */
export const servingSources = (
  view: SettingsSourcesView | undefined,
): ServingSource[] =>
  (view?.sources ?? []).flatMap((item) =>
    item.status === "serving" && item.id
      ? [
          {
            id: item.id,
            writable:
              item.scope.write === null || (item.scope.write?.length ?? 0) > 0,
          },
        ]
      : [],
  );
