import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect } from "react";
import { ErrorBoundary } from "react-error-boundary";

import { ConfirmDialogProvider } from "@/app/confirm-dialog";
import { ErrorFallback } from "@/app/error-fallback";
import { Toaster } from "@/shared/components/ui/sonner";
import { TooltipProvider } from "@/shared/components/ui/tooltip";
import { usePreferencesStore } from "@/shared/stores/preferences";

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** 設定の明暗を `<html>` の `dark` クラスに反映する（`system` は `prefers-color-scheme` に合わせる） */
const useColorScheme = (): void => {
  const colorScheme = usePreferencesStore((state) => state.colorScheme);
  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    const apply = () => {
      const dark = colorScheme === "dark" || (colorScheme === "system" && media?.matches === true);
      document.documentElement.classList.toggle("dark", dark);
    };
    apply();
    media?.addEventListener?.("change", apply);
    return () => media?.removeEventListener?.("change", apply);
  }, [colorScheme]);
};

type Props = { queryClient: QueryClient; children: ReactNode };

/** 画面全体の Provider */
export const AppProviders = ({ queryClient, children }: Props) => {
  useColorScheme();
  return (
    <ErrorBoundary FallbackComponent={({ error }) => <ErrorFallback error={error} />}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <ConfirmDialogProvider>
            {children}
            <Toaster />
          </ConfirmDialogProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
