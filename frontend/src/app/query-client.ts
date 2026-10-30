import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { handleAppError } from "@/shared/core/handle-app-error";

const SIXTY_SECONDS = 60_000;

type HandleErrorMeta = { handleError?: boolean } | undefined;

const handles = (meta: HandleErrorMeta): boolean => meta?.handleError !== false;

/** 画面の既定の QueryClient を作る */
export const createQueryClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: SIXTY_SECONDS,
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (handles(query.meta as HandleErrorMeta)) handleAppError(error);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (handles(mutation.meta as HandleErrorMeta)) handleAppError(error);
      },
    }),
  });
