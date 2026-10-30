import { createFileRoute } from "@tanstack/react-router";

import { SettingsScreen } from "@/features/settings/settings/settings-screen";
import { getSettingsGetSettingsSourcesQueryOptions } from "@/shared/api/generated/settings/settings";

export const Route = createFileRoute("/_settings")({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData(getSettingsGetSettingsSourcesQueryOptions()),
  component: SettingsScreen,
  pendingMs: 1000,
});
