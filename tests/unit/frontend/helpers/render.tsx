import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";


export const createTestQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

/** メモリの履歴のルーターに部品を置く。画面のルートの形（/$source/・/$source/$・/_settings）だけを持つ */
export function renderInRouter(ui: ReactNode, path = "/s/a.md", queryClient = createTestQueryClient()) {
  const rootRoute = createRootRoute({ component: () => <>{ui}</> });
  const sourceRoute = createRoute({ getParentRoute: () => rootRoute, path: "/$source/" });
  const docRoute = createRoute({ getParentRoute: () => rootRoute, path: "/$source/$" });
  const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/_settings" });
  const router = createRouter({
    routeTree: rootRoute.addChildren([sourceRoute, docRoute, settingsRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, queryClient, ...view };
}
