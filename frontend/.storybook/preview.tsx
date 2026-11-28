import { withThemeByClassName } from "@storybook/addon-themes";
import type { Decorator, Preview } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { mswLoader } from "msw-storybook-addon/csf3";

import { ConfirmDialogProvider } from "../src/app/confirm-dialog";
import "../src/shared/styles/index.css";

/**
 * Link を使用できるよう、メモリの履歴のルーターに story を配置する（`parameters.initialPath` で開く URL を選ぶ）。
 * 離脱の警告が確認のダイアログを開くため、確認のダイアログの Provider の中に置く
 */
const withRouter: Decorator = (Story, context) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const root = createRootRoute({ component: () => <Story /> });
  const routes = ["/", "/$source/", "/$source/_metadata", "/$source/$", "/_settings"].map((path) =>
    createRoute({ getParentRoute: () => root, path }),
  );
  const router = createRouter({
    routeTree: root.addChildren(routes),
    history: createMemoryHistory({
      initialEntries: [(context.parameters.initialPath as string | undefined) ?? "/sample/docs/a"],
    }),
  });
  return (
    <QueryClientProvider client={client}>
      <ConfirmDialogProvider>
        <RouterProvider router={router} />
      </ConfirmDialogProvider>
    </QueryClientProvider>
  );
};

const preview: Preview = {
  loaders: [mswLoader()],
  decorators: [
    withRouter,
    withThemeByClassName({
      themes: { light: "", dark: "dark" },
      defaultTheme: "light",
    }),
  ],
  parameters: { layout: "fullscreen", a11y: { test: "error" } },
};

export default preview;
