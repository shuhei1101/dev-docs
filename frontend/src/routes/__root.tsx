import { Outlet, createRootRouteWithContext } from "@tanstack/react-router";

import { ErrorFallback } from "@/app/error-fallback";
import type { RouterContext } from "@/app/router";
import { NotFoundScreen } from "@/features/docs/not-found/not-found-screen";

export const Route = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: () => <NotFoundScreen />,
  errorComponent: ({ error }) => <ErrorFallback error={error} />,
});
