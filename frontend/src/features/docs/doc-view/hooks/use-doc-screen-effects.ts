import { useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";

import { useLastDocStore } from "@/shared/stores/last-doc";

/** ブラウザのタブのタイトルを合わせ、開いている文書の URL を設定画面から戻れるように覚える */
export const useDocScreenEffects = (title: string, source: string): void => {
  useEffect(() => {
    document.title = title;
  }, [title]);
  const href = useRouterState({ select: (state) => state.location.href });
  const setLastDoc = useLastDocStore((state) => state.setHref);
  useEffect(() => {
    // 他の画面へ移る途中の URL は覚えない
    if (href === `/${source}` || href.startsWith(`/${source}/`))
      setLastDoc(href);
  }, [href, source, setLastDoc]);
};
