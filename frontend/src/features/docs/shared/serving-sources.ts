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

export type UnservedSource = { source: string; reason: string };

/** 端末の設定の取得から、project-index が起動時の検証で除外した配信元と理由を取り出す */
export const unservedSources = (
  view: SettingsSourcesView | undefined,
): UnservedSource[] =>
  (view?.sources ?? []).flatMap((item) =>
    item.status === "not_served" && item.id
      ? [
          {
            source: item.id,
            reason: [
              "project-index が起動時の検証で除外しました。",
              ...(item.errors ?? []).map(
                (error) => `${error.path} ${error.reason}`,
              ),
            ].join(" "),
          },
        ]
      : [],
  );
