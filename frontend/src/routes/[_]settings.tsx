import { createFileRoute } from "@tanstack/react-router";

import { SettingsScreen } from "@/features/settings/settings/settings-screen";

export const Route = createFileRoute("/_settings")({
  component: SettingsScreen,
});
