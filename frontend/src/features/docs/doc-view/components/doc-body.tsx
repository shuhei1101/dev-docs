import { useNavigate, useSearch } from "@tanstack/react-router";
import { type MouseEvent, useEffect, useRef } from "react";

import { useColumnPersistence } from "@/features/docs/doc-view/hooks/use-column-persistence";
import { useMdmark } from "@/features/docs/doc-view/hooks/use-mdmark";
import { findActivePage } from "@/features/docs/doc-view/nav";
import { type TocItem, readToc } from "@/features/docs/doc-view/toc";
import {
  type DocComment,
  commentsOf,
  useCommentStore,
} from "@/features/docs/shared/comments/comment-store";
import type { DocumentResponse } from "@/shared/api/generated/model";

type Props = {
  document: DocumentResponse;
  onHeadings: (items: TocItem[]) => void;
  onCommentSaved: () => void;
  /** コメントのパネルで場所を選ばれたコメント。印が見つかったら `onLocated` で戻す */
  locating: DocComment | null;
  onLocated: () => void;
};

const TABLE_MARKER = /<!--\s*table:[^>]*-->/g;

/** 最初の見出し 1 は文書のタイトルに出すため除く */
const withoutFirstH1 = (markdown: string): string =>
  markdown.replace(/^\s*# .*\n?/, "");

/** 隠す列を、その表のマーカー（`+columns` の表）へ `hide=` で書き込む */
export const applyHiddenColumns = (
  markdown: string,
  tableKeys: string[],
  columns: Record<string, string[]>,
): string => {
  let index = 0;
  return markdown.replace(TABLE_MARKER, (marker) => {
    const key = tableKeys[index++];
    const hidden = key === undefined ? undefined : columns[key];
    if (!marker.includes("+columns") || !hidden?.length) return marker;
    return marker.replace(/\s*-->$/, ` hide=${hidden.join(",")} -->`);
  });
};

/** 引用の前にある見出しを階層ごとに取る */
const headingsBefore = (
  root: HTMLElement,
  quote: string,
  prefix: string,
  suffix: string,
): string[] => {
  const text = root.textContent ?? "";
  const at = text.indexOf(`${prefix}${quote}${suffix}`);
  const position = at < 0 ? text.indexOf(quote) : at + prefix.length;
  if (position < 0) return [];
  const result: Array<string | undefined> = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let offset = 0;
  const headings = Array.from(root.querySelectorAll("h1, h2, h3, h4, h5, h6"));
  for (const heading of headings) {
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (heading.contains(node)) break;
      offset += node.textContent?.length ?? 0;
    }
    if (offset > position) break;
    const level = Number(heading.tagName.slice(1));
    result[level] = heading.textContent ?? "";
    result.length = level + 1;
  }
  return result.filter((item): item is string => item !== undefined);
};

/** 選んだ文字列が一致するコメントの印を探す */
const findCommentMark = (root: HTMLElement, quote: string) =>
  Array.from(root.querySelectorAll(".mdmark-comment-mark")).find(
    (mark) => mark.textContent?.trim() === quote.trim(),
  );

/** mdmark で描く文書の本文。リンクとコメントを画面とつなぐ */
export const DocBody = ({
  document: doc,
  onHeadings,
  onCommentSaved,
  locating,
  onLocated,
}: Props) => {
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const search = useSearch({ strict: false }) as {
    rev?: string;
    base?: string;
  };
  const docId = `${doc.source}@${doc.ref ?? ""}:${doc.path}`;
  const markdown = applyHiddenColumns(
    withoutFirstH1(doc.markdown ?? ""),
    doc.tableKeys,
    doc.columns,
  );
  const title = findActivePage(doc.tabs, doc.path).page?.title ?? doc.path;

  const { ready } = useMdmark(ref, {
    markdown,
    docId,
    // コメントの機能は mdmark の既定でオフなので、オンにする
    config: { features: { comments: true } },
    commentStore: {
      load: ({ docId: id }) =>
        Promise.resolve(commentsOf(useCommentStore.getState().comments, id)),
      save: ({ comment }) => {
        const element = ref.current;
        const saved = useCommentStore.getState().add({
          ...comment,
          docId,
          source: doc.source,
          ref: doc.ref ?? null,
          path: doc.path,
          docTitle: title,
          headings: element
            ? headingsBefore(
                element,
                comment.quote,
                comment.prefix,
                comment.suffix,
              )
            : [],
        });
        onCommentSaved();
        return Promise.resolve({
          id: saved.id,
          quote: saved.quote,
          prefix: saved.prefix,
          suffix: saved.suffix,
          body: saved.body,
        });
      },
    },
  });

  useColumnPersistence(ref, doc.source, doc.tableKeys);

  useEffect(() => {
    if (ready && ref.current) onHeadings(readToc(ref.current));
  }, [ready, markdown, onHeadings]);

  // 場所を選ばれたコメントの印へスクロールする（印は mdmark がコメントを読み込んだ後に描く）
  useEffect(() => {
    const root = ref.current;
    if (!ready || !root || locating === null || locating.docId !== docId)
      return;
    const find = () => {
      const mark = findCommentMark(root, locating.quote);
      if (mark === undefined) return false;
      mark.scrollIntoView({ block: "center" });
      onLocated();
      return true;
    };
    if (find()) return;
    const observer = new MutationObserver(() => {
      if (find()) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [ready, locating, docId, onLocated]);

  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const anchor = (event.target as HTMLElement).closest("a[href]");
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    if (/^[a-z][a-z0-9+.-]*:|^\/\//i.test(href)) {
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener");
      return;
    }
    if (href.startsWith("#")) return;
    event.preventDefault();
    const url = new URL(
      href,
      `${window.location.origin}/${doc.source}/${doc.path}`,
    );
    const prefix = `/${doc.source}/`;
    if (!url.pathname.startsWith(prefix)) return;
    void navigate({
      to: "/$source/$",
      params: {
        source: doc.source,
        _splat: decodeURIComponent(url.pathname.slice(prefix.length)),
      },
      search: { rev: search.rev, base: search.base },
    });
  };

  // 本文の中のリンクは mdmark が描く。キーボード操作は a 要素の既定の動きに任せる
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div ref={ref} onClick={onClick} className="min-w-0" />
  );
};
