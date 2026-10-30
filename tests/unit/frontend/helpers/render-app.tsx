import { RouterProvider } from "@tanstack/react-router";
import { render } from "@testing-library/react";

import { AppProviders } from "@/app/providers";
import { createQueryClient } from "@/app/query-client";
import { createAppRouter } from "@/app/router";

/** 本物のルートの木で画面を開く（ブラウザの履歴に path を置いてからルーターを作る） */
export const renderApp = (path: string) => {
  window.history.pushState({}, "", path);
  const queryClient = createQueryClient();
  const router = createAppRouter({ queryClient });
  const view = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { router, queryClient, ...view };
};
