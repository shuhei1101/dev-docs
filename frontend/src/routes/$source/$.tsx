import { createFileRoute } from "@tanstack/react-router";

import { DocViewScreen } from "@/features/docs/doc-view/doc-view-screen";
import { loadDocument } from "@/features/docs/doc-view/queries";
import { DocViewSearchSchema } from "@/features/docs/doc-view/search";
import { KEEP_PREVIOUS_MS } from "@/app/pending";
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
  pendingMs: KEEP_PREVIOUS_MS,
});
