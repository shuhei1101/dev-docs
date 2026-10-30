import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { notFound } from "@tanstack/react-router";

import type { RouterContext } from "@/app/router";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import {
  getViewGetDocumentDefaultQueryKey,
  viewGetDocument,
  viewGetDocumentDefault,
} from "@/shared/api/generated/view/view";
import { NotFoundError } from "@/shared/core/app-error";

/** 文書の取得の `queryOptions`（パスが空なら `view-get_document_default`、あれば `view-get_document`） */
export const documentQueryOptions = (source: string, path: string, search: DocViewSearch) =>
  queryOptions({
    queryKey: ["view", "document", source, path, search.rev, search.base],
    queryFn: ({ signal }) => {
      const params = { ref: search.rev, diff: search.base };
      return path === ""
        ? viewGetDocumentDefault(source, params, { signal })
        : viewGetDocument(source, path, params, { signal });
    },
    meta: { handleError: false },
    placeholderData: keepPreviousData,
  });

/** 目次の変更のマーカーに使う、比較元のリビジョンの同じ文書の `markdown`。比較元に無ければ null */
export const baseMarkdownQueryOptions = (source: string, path: string, base: string | null) =>
  queryOptions({
    queryKey: ["view", "base-markdown", source, path, base],
    enabled: base !== null,
    meta: { handleError: false },
    queryFn: async ({ signal }): Promise<string | null> => {
      try {
        const response = await viewGetDocument(source, path, { ref: base ?? undefined }, { signal });
        return response.markdown ?? null;
      } catch (error) {
        if (error instanceof NotFoundError) return null;
        throw error;
      }
    },
  });

/** ルートの loader。文書を読み、404 は見つからない画面へ回す */
export const loadDocument = async ({
  context,
  params,
  deps,
}: {
  context: RouterContext;
  params: { source: string; _splat?: string };
  deps: DocViewSearch;
}): Promise<void> => {
  try {
    await context.queryClient.ensureQueryData(
      documentQueryOptions(params.source, params._splat ?? "", deps),
    );
  } catch (error) {
    if (error instanceof NotFoundError) throw notFound({ data: error.problem });
    throw error;
  }
};

export { getViewGetDocumentDefaultQueryKey };
