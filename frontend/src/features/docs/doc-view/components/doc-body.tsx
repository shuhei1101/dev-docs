import { useNavigate, useSearch } from "@tanstack/react-router";
import { type MouseEvent, useEffect, useRef } from "react";

import { useColumnPersistence } from "@/features/docs/doc-view/hooks/use-column-persistence";
import { useMdmark } from "@/features/docs/doc-view/hooks/use-mdmark";
import { findActivePage } from "@/features/docs/doc-view/nav";
import { applyHiddenColumns, columnTableKeys } from "@/features/docs/doc-view/tables";
import { type TocItem, readToc } from "@/features/docs/doc-view/toc";
import {
  type DocComment,
  commentsOf,
  docIdOf,
  useCommentStore,
} from "@/features/docs/shared/comments/comment-store";
import type { DocumentResponse } from "@/shared/api/generated/model";

type Props = {
  document: DocumentResponse;
  /** 比較元の文書の本文と表のキー（差分の強調）。null・省略は強調しない */
  baseMarkdown?: { markdown: string; tableKeys: string[] } | null;
  onHeadings: (items: TocItem[]) => void;
  onCommentSaved: () => void;
  /** コメントのパネルで場所を選ばれたコメント。その箇所へ移ったら `onLocated` で戻す */
  locating: DocComment | null;
  onLocated: () => void;
};

/** 最初の見出し 1 は文書のタイトルに出すため除く */
const withoutFirstH1 = (markdown: string): string =>
  markdown.replace(/^\s*# .*\n?/, "");

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

/** mdmark で描く文書の本文。リンクとコメントを画面とつなぐ */
export const DocBody = ({
  document: doc,
  baseMarkdown,
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
  const docId = docIdOf(doc);
  const markdown = applyHiddenColumns({
    markdown: withoutFirstH1(doc.markdown ?? ""),
    tableKeys: doc.tableKeys,
    columns: doc.columns,
  });
  // 比較元にも、本文と同じ見出し 1 の除去と隠す列の書き込みを適用して比べる
  const base = baseMarkdown
    ? applyHiddenColumns({
        markdown: withoutFirstH1(baseMarkdown.markdown),
        tableKeys: baseMarkdown.tableKeys,
        columns: doc.columns,
      })
    : null;
  const onColumnsChange = useColumnPersistence({
    source: doc.source,
    columnKeys: columnTableKeys({ markdown, tableKeys: doc.tableKeys }),
  });
  // この文書のコメントの並び（変わったら本文のマーカーを再描画する）
  const commentSignature = useCommentStore((state) =>
    commentsOf(state.comments, docId)
      .map((item) => `${item.id}:${item.body}`)
      .join("\n"),
  );
  const title = findActivePage(doc.tabs, doc.path).page?.title ?? doc.path;

  const { ready, handle } = useMdmark(ref, {
    markdown,
    baseMarkdown: base,
    onColumnsChange,
    docId,
    aliases: doc.aliases,
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
      update: ({ id, body }) => {
        useCommentStore.getState().update(id, body);
        return Promise.resolve();
      },
      remove: ({ id }) => {
        useCommentStore.getState().remove(id);
        return Promise.resolve();
      },
    },
  });

  // コメントの保存先のこの文書のコメントが変わったら、本文のマーカーを再描画する（描いた直後の並びは再描画しない）
  const shown = useRef<{ docId: string; signature: string } | null>(null);
  useEffect(() => {
    if (!ready || handle === null) return;
    if (shown.current?.docId !== docId) {
      shown.current = { docId, signature: commentSignature };
      return;
    }
    if (shown.current.signature === commentSignature) return;
    shown.current = { docId, signature: commentSignature };
    void handle.reloadComments();
  }, [ready, handle, docId, commentSignature]);

  useEffect(() => {
    if (ready && ref.current) onHeadings(readToc(ref.current));
  }, [ready, markdown, onHeadings]);

  // 場所を選ばれたコメントへ移る（コメントを再取得してから、その箇所を画面に入れて強調する）
  useEffect(() => {
    if (!ready || handle === null || locating === null || locating.docId !== docId)
      return;
    let cancelled = false;
    void handle.reloadComments().then(() => {
      if (cancelled) return;
      handle.focusComment(locating.id);
      onLocated();
    });
    return () => {
      cancelled = true;
    };
  }, [ready, handle, locating, docId, onLocated]);

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
    // 管理用の YAML の行の文書は、画面のパスではなく本文のファイルのパスを基準に解決する
    const url = new URL(
      href,
      `${window.location.origin}/${doc.source}/${doc.bodyPath ?? doc.path}`,
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
