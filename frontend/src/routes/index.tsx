import { createFileRoute, redirect } from "@tanstack/react-router";

import type { RouterContext } from "@/app/router";
import { getSettingsGetSettingsSourcesQueryOptions } from "@/shared/api/generated/settings/settings";

/** 端末の設定の配信元のうち最初の配信中のものへ、無ければ設定画面へ移す */
export const redirectToFirstSource = async ({
  context,
}: {
  context: RouterContext;
}): Promise<never> => {
  const view = await context.queryClient.ensureQueryData(
    getSettingsGetSettingsSourcesQueryOptions(),
  );
  const serving = view.sources.find((source) => source.status === "serving" && source.id);
  if (serving?.id) {
    throw redirect({ to: "/$source", params: { source: serving.id }, replace: true });
  }
  throw redirect({ to: "/_settings", replace: true });
};

export const Route = createFileRoute("/")({ loader: redirectToFirstSource });
