import { useParams, useSearch } from "@tanstack/react-router";

import { describeMissing } from "@/features/docs/not-found/missing";
import { servingSources } from "@/features/docs/shared/serving-sources";
import { useSettingsGetSettingsSources } from "@/shared/api/generated/settings/settings";
import { useViewListRefs } from "@/shared/api/generated/view/view";
import { MissingSchema } from "@/shared/core/schema";

/** 見つからない画面に出す内容と、読んだ配信元・リビジョンの一覧 */
export const useMissingView = (data: unknown) => {
  const params = useParams({ strict: false }) as { source?: string };
  const search = useSearch({ strict: false }) as { rev?: string };
  const kind = MissingSchema.safeParse(data).data?.missing;
  // 無い配信元・配信していない配信元のときは、リビジョンの一覧を読まない
  const source =
    kind === "source" || kind === "not_served" ? undefined : params.source;
  const settings = useSettingsGetSettingsSources().data;
  const refs = useViewListRefs(source ?? "", undefined, {
    query: { enabled: source !== undefined && kind !== undefined },
  }).data;
  const missing = describeMissing(data, {
    defaultRef: refs?.defaultRef,
    configs: settings?.sources.find((item) => item.id === params.source)
      ?.config,
    source: params.source,
    ref: refs?.git === false ? undefined : (search.rev ?? refs?.defaultRef),
  });
  return {
    source,
    urlSource: params.source,
    rev: search.rev,
    refs,
    missing,
    serving: servingSources(settings),
  };
};
