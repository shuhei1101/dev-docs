import { createFileRoute } from "@tanstack/react-router";

import { DocSkeleton } from "@/features/docs/doc-view/components/doc-skeleton";
import { DocViewScreen } from "@/features/docs/doc-view/doc-view-screen";
import { loadDocument } from "@/features/docs/doc-view/queries";
import { DocViewSearchSchema } from "@/features/docs/doc-view/search";
import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";

export const Route = createFileRoute("/$source/$")({
  validateSearch: DocViewSearchSchema,
  loaderDeps: ({ search }) => search,
  loader: ({ context, params, deps }) =>
    loadDocument({
      context,
      params: { source: params.source, _splat: params._splat },
      deps,
    }),
  component: DocViewScreen,
  notFoundComponent: ({ data }) => <NotFoundScreen data={data} />,
  pendingComponent: DocSkeleton,
  pendingMs: 1000,
});
