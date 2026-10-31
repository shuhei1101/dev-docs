import type { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";

import { ErrorFallback } from "@/app/error-fallback";
import { routeTree } from "@/route-tree.gen";

/** ルートの `loader` が使う依存 */
export type RouterContext = { queryClient: QueryClient };

/** クエリを文字列のまま読む（数字だけのリビジョン＝commit の短縮 ID を数値にしない） */
export const parseSearch = (search: string): Record<string, string> =>
  Object.fromEntries(new URLSearchParams(search));

/** クエリを文字列のまま書く（値が `undefined` のキーは書かない） */
export const stringifySearch = (search: Record<string, unknown>): string => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (value !== undefined && value !== null) params.set(key, String(value));
  }
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
};

/** ルートの木と文脈でルーターを作る */
export const createAppRouter = (context: RouterContext) =>
  createRouter({
    routeTree,
    context,
    defaultPreload: "intent",
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
    parseSearch,
    stringifySearch,
    defaultErrorComponent: ({ error }) => <ErrorFallback error={error} />,
  });

declare module "@tanstack/react-router" {
  // eslint-disable-next-line @typescript-eslint/consistent-type-definitions -- declaration merging
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
