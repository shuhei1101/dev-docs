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

import "../src/index.css";

/** Link が使えるよう、メモリの履歴のルーターに story を置く */
const withRouter: Decorator = (Story) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const root = createRootRoute({ component: () => <Story /> });
  const routes = ["/", "/$source/", "/$source/$", "/_settings"].map((path) =>
    createRoute({ getParentRoute: () => root, path }),
  );
  const router = createRouter({
    routeTree: root.addChildren(routes),
    history: createMemoryHistory({ initialEntries: ["/sample/docs/a"] }),
  });
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
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
