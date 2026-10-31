import { useState } from "react";

import type { DocComment } from "@/features/docs/shared/comments/comment-store";

/**
 * コメントのパネルで場所を選ばれたコメントを持つ。
 * 開いている文書が、そのコメントの文書と違う文書に変わったら戻す
 */
export const useLocating = (
  docId: string,
  openDoc: (comment: DocComment) => void,
) => {
  const [locating, setLocating] = useState<DocComment | null>(null);
  const [openedDocId, setOpenedDocId] = useState(docId);
  if (openedDocId !== docId) {
    setOpenedDocId(docId);
    if (locating !== null && locating.docId !== docId) setLocating(null);
  }
  return {
    locating,
    onLocated: () => setLocating(null),
    // 開いている文書のコメントは移動せず、本文の印までスクロールするだけにする
    locate: (comment: DocComment) => {
      setLocating(comment);
      if (comment.docId !== docId) openDoc(comment);
    },
  };
};
