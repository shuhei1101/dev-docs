import {
  Link,
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { type ConfirmRequest, ConfirmDialogProvider } from "@/app/confirm-dialog";
import { useLeaveGuard } from "@/shared/hooks/use-leave-guard";

const NAVIGATION: ConfirmRequest = {
  title: "入力した内容を破棄して移動しますか?",
  description: "配信元のダイアログに入力した内容は保存されていません。",
  confirmLabel: "破棄して移動",
  destructive: true,
};

const renderGuard = (active: boolean, navigation?: ConfirmRequest) => {
  const Guarded = () => {
    useLeaveGuard(active, { navigation });
    return <Link to="/_settings">別の画面</Link>;
  };
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const routeTree = rootRoute.addChildren([
    createRoute({ getParentRoute: () => rootRoute, path: "/", component: Guarded }),
    createRoute({ getParentRoute: () => rootRoute, path: "/_settings", component: () => <p>別の画面です</p> }),
  ]);
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: ["/"] }) });
  render(
    <ConfirmDialogProvider>
      <RouterProvider router={router} />
    </ConfirmDialogProvider>,
  );
  return router;
};

const fireBeforeUnload = () => {
  const event = new Event("beforeunload", { cancelable: true });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
};

test("test_use_leave_guard_when_active", async () => {
  renderGuard(true);
  await screen.findByRole("link", { name: "別の画面" });

  expect(fireBeforeUnload().defaultPrevented).toBe(true);
});

test("test_use_leave_guard_when_inactive", async () => {
  const router = renderGuard(false, NAVIGATION);
  await screen.findByRole("link", { name: "別の画面" });

  expect(fireBeforeUnload().defaultPrevented).toBe(false);
  await userEvent.click(screen.getByRole("link", { name: "別の画面" }));

  await waitFor(() => expect(router.state.location.pathname).toBe("/_settings"));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

test("test_use_leave_guard_when_navigation_cancelled", async () => {
  const router = renderGuard(true, NAVIGATION);
  await userEvent.click(await screen.findByRole("link", { name: "別の画面" }));

  const dialog = await screen.findByRole("alertdialog");
  expect(dialog).toHaveTextContent(NAVIGATION.title);
  expect(dialog).toHaveTextContent(String(NAVIGATION.description));
  await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));

  await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  expect(router.state.location.pathname).toBe("/");
});

test("test_use_leave_guard_when_navigation_confirmed", async () => {
  const router = renderGuard(true, NAVIGATION);
  await userEvent.click(await screen.findByRole("link", { name: "別の画面" }));

  await userEvent.click(await screen.findByRole("button", { name: "破棄して移動" }));

  await waitFor(() => expect(router.state.location.pathname).toBe("/_settings"));
});
