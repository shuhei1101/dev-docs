import { useRef } from "react";

import { type MdmarkCommentStore, useMdmark } from "@/features/docs/doc-view/hooks/use-mdmark";

/** プレビューはコメントを持たない */
const NO_COMMENTS: MdmarkCommentStore = {
  load: () => Promise.resolve([]),
  save: () => Promise.reject(new Error("プレビューにはコメントを付けられません")),
  update: () => Promise.resolve(),
  remove: () => Promise.resolve(),
};

type Props = { markdown: string; docId: string };

/** 編集中の Markdown を mdmark で描いたプレビュー */
export const MarkdownPreview = ({ markdown, docId }: Props) => {
  const ref = useRef<HTMLDivElement>(null);
  useMdmark(ref, { markdown, docId: `preview:${docId}`, commentStore: NO_COMMENTS });
  return <div ref={ref} className="min-w-0" />;
};
