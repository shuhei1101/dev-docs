import {
  type QueryClient,
  keepPreviousData,
  queryOptions,
} from "@tanstack/react-query";
import { notFound } from "@tanstack/react-router";

import type { DocViewSearch } from "@/features/docs/doc-view/search";
import {
  getViewGetDocumentDefaultQueryKey,
  viewGetDocument,
  viewGetDocumentDefault,
} from "@/shared/api/generated/view/view";
import { NotFoundError } from "@/shared/core/app-error";

/** 文書の取得の `queryOptions`（パスが空なら `view-get_document_default`、あれば `view-get_document`） */
export const documentQueryOptions = (
  source: string,
  path: string,
  search: DocViewSearch,
) =>
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

/** 本文の差分の強調に使用する、比較元のリビジョンの同じ文書の `markdown` と `tableKeys`。比較元に無いか本文が無ければ null */
export const baseMarkdownQueryOptions = (
  source: string,
  path: string,
  base: string | null,
) =>
  queryOptions({
    queryKey: ["view", "base-markdown", source, path, base],
    enabled: base !== null,
    meta: { handleError: false },
    queryFn: async ({
      signal,
    }): Promise<{ markdown: string; tableKeys: string[] } | null> => {
      try {
        const response = await viewGetDocument(
          source,
          path,
          { ref: base ?? undefined },
          { signal },
        );
        if (response.markdown == null) return null;
        return { markdown: response.markdown, tableKeys: response.tableKeys };
      } catch (error) {
        if (error instanceof NotFoundError) return null;
        throw error;
      }
    },
  });

type LoaderContext = { queryClient: QueryClient };

/** ルートの loader。文書を取得し、404 は見つからない画面へ回す */
export const loadDocument = async ({
  context,
  params,
  deps,
}: {
  context: LoaderContext;
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
