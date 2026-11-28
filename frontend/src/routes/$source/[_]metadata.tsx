import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

import { MetadataScreen } from "@/features/metadata/metadata/metadata-screen";

/** メタデータの画面の URL のクエリ。`tab` は種類、`panel` が `edits` でレビュー中のパネルを開く */
const MetadataSearchSchema = z.object({
  tab: z.string().min(1).optional().catch(undefined),
  panel: z.literal("edits").optional().catch(undefined),
});

const MetadataRoute = () => {
  const { source } = Route.useParams();
  return <MetadataScreen source={source} />;
};

export const Route = createFileRoute("/$source/_metadata")({
  validateSearch: MetadataSearchSchema,
  component: MetadataRoute,
});
