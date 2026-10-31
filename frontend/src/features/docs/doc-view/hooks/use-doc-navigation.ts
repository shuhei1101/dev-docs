import { useNavigate } from "@tanstack/react-router";

import type { DocViewSearch } from "@/features/docs/doc-view/search";
import type { DocComment } from "@/features/docs/shared/comments/comment-store";
import type { RefsResponse } from "@/shared/api/generated/model";

type Target = { splat: string; rev?: string; base?: string };

/** 比較を始めるときの比較元（開いているのが既定のリビジョン以外なら既定、既定なら最近の commit の 2 件目） */
export const compareBase = (
  refs: RefsResponse | undefined,
  rev: string | undefined,
) => {
  if (refs === undefined) return undefined;
  return (rev ?? refs.defaultRef) !== refs.defaultRef
    ? refs.defaultRef
    : refs.commits?.[1]?.commit;
};

/** 文書の画面から別の文書・リビジョンへ移る操作 */
export const useDocNavigation = (
  source: string,
  path: string,
  search: DocViewSearch,
  refs: RefsResponse | undefined,
) => {
  const navigate = useNavigate();
  const go = ({ splat, rev, base }: Target) =>
    void navigate({
      to: "/$source/$",
      params: { source, _splat: splat },
      search: { rev, base },
    });
  return {
    openDoc: (splat: string) => go({ splat, rev: search.rev }),
    selectRef: (rev: string) => go({ splat: path, rev, base: search.base }),
    compare: (rev: string | undefined, base: string) =>
      go({ splat: path, rev, base }),
    clearDiff: () => go({ splat: path, rev: search.rev }),
    startCompare: () => {
      const base = compareBase(refs, search.rev);
      if (base) go({ splat: path, rev: search.rev, base });
    },
    selectSource: (id: string) =>
      void navigate({ to: "/$source", params: { source: id } }),
    locate: (comment: DocComment) =>
      void navigate({
        to: "/$source/$",
        params: { source: comment.source, _splat: comment.path },
        search: { rev: comment.ref ?? undefined },
      }),
  };
};
