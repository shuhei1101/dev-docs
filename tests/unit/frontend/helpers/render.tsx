import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createBrowserHistory,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";


export const createTestQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

/**
 * メモリの履歴のルーターに部品を配置する。画面のルートの構造（/$source/・/$source/$・/_settings）だけを持つ。
 * `browser` を true にすると、タブを閉じる・再読み込みの警告（beforeunload）を受けるブラウザの履歴にする
 */
export function renderInRouter(
  ui: ReactNode,
  path = "/s/a.md",
  queryClient = createTestQueryClient(),
  { browser = false }: { browser?: boolean } = {},
) {
  if (browser) window.history.replaceState({}, "", path);
  const rootRoute = createRootRoute({ component: () => <>{ui}</> });
  const sourceRoute = createRoute({ getParentRoute: () => rootRoute, path: "/$source/" });
  const docRoute = createRoute({ getParentRoute: () => rootRoute, path: "/$source/$" });
  const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/_settings" });
  const router = createRouter({
    routeTree: rootRoute.addChildren([sourceRoute, docRoute, settingsRoute]),
    history: browser ? createBrowserHistory() : createMemoryHistory({ initialEntries: [path] }),
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, queryClient, ...view };
}
