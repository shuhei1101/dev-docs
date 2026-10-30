import type { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";

import { ErrorFallback } from "@/app/error-fallback";
import { routeTree } from "@/route-tree.gen";

/** ルートの `loader` が使う依存 */
export type RouterContext = { queryClient: QueryClient };

/** ルートの木と文脈でルーターを作る */
export const createAppRouter = (context: RouterContext) =>
  createRouter({
    routeTree,
    context,
    defaultPreload: "intent",
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
    defaultErrorComponent: ({ error }) => <ErrorFallback error={error} />,
  });

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
