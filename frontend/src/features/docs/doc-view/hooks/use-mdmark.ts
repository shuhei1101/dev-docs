import { type RefObject, useEffect, useRef, useState } from "react";

import type { AliasItem } from "@/shared/api/generated/model";
import { logger } from "@/shared/lib/logger";

/** mdmark の読み込み先（jsDelivr の GitHub の master ブランチの URL。master に入った mdmark のリリースを読む） */
export const MDMARK_URL =
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@master/dist/index.js";

/** mdmark のスタイル */
export const MDMARK_CSS_URL =
  "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@master/dist/index.css";

export type MdmarkComment = {
  id: string;
  quote: string;
  prefix: string;
  suffix: string;
  body: string;
};

export type MdmarkCommentDraft = Omit<MdmarkComment, "id">;

export type MdmarkCommentStore = {
  load: (target: { docId: string }) => Promise<MdmarkComment[]>;
  save: (target: {
    docId: string;
    comment: MdmarkCommentDraft;
  }) => Promise<MdmarkComment>;
};

export type MdmarkOptions = {
  markdown: string;
  docId: string;
  /** 文書の取得の `aliases`（mdmark の索引にして渡す） */
  aliases?: AliasItem[];
  commentStore: MdmarkCommentStore;
  /** 機能のオン・オフ（`comments` は既定でオフ） */
  config?: { features?: Record<string, boolean> };
};

export type MdmarkIndexDoc = {
  id: string;
  path: string;
  title: string;
  description?: string;
  aliases: string[];
};

export type MdmarkIndexTerm = {
  id: string;
  term: string;
  aliases: string[];
  meaning: string;
  avoid?: string[];
};

export type MdmarkIndex = { docs: MdmarkIndexDoc[]; terms: MdmarkIndexTerm[] };

type MdmarkMountOptions = Omit<MdmarkOptions, "aliases"> & { index: MdmarkIndex };

export type MdmarkHandle = {
  update: (markdown: string) => void;
  destroy: () => void;
};

type MdmarkModule = {
  mount: (element: HTMLElement, options: MdmarkMountOptions) => MdmarkHandle;
};

let loading: Promise<MdmarkModule> | null = null;

/** 文書の取得の `aliases` を mdmark の `opts.index`（`docs`・`terms`）にする */
export const toMdmarkIndex = (aliases: AliasItem[]): MdmarkIndex => {
  const terms: MdmarkIndexTerm[] = [];
  const docs: MdmarkIndexDoc[] = [];
  for (const item of aliases) {
    if (item.aliasType === "term") {
      // 説明の無い用語は mdmark が除くので載せない
      if (!item.description) continue;
      terms.push({
        id: item.id,
        term: item.name,
        aliases: item.aliases,
        meaning: item.description,
        ...(item.avoid ? { avoid: item.avoid } : {}),
      });
    } else if (item.aliasType === "doc") {
      docs.push({
        id: item.id,
        path: item.id,
        title: item.name,
        ...(item.description ? { description: item.description } : {}),
        aliases: item.aliases,
      });
    }
  }
  return { docs, terms };
};

/** スタイルを `document.head` に 1 回だけ置く */
const ensureStylesheet = (): void => {
  if (document.head.querySelector(`link[href="${MDMARK_CSS_URL}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = MDMARK_CSS_URL;
  document.head.append(link);
};

/** mdmark をモジュールの中で 1 回だけ読む */
const load = (): Promise<MdmarkModule> => {
  ensureStylesheet();
  loading ??= import(/* @vite-ignore */ MDMARK_URL).catch((error: unknown) => {
    loading = null;
    throw error;
  });
  return loading;
};

type State = {
  handle: MdmarkHandle | null;
  ready: boolean;
  error: unknown;
  /** `handle` が描いている文書 */
  docId: string | null;
};

/** 要素に mdmark で本文を描き、本文の変更で `update`、外れるときに `destroy` する。`ready` は今の文書を描き終えたとき `true` */
export const useMdmark = (
  ref: RefObject<HTMLElement | null>,
  options: MdmarkOptions,
): State => {
  const [state, setState] = useState<State>({
    handle: null,
    ready: false,
    error: null,
    docId: null,
  });
  const latest = useRef(options);
  const rendered = useRef(options.markdown);
  useEffect(() => {
    latest.current = options;
  });

  // 文書が変わったら破棄して描き直す
  useEffect(() => {
    let cancelled = false;
    let handle: MdmarkHandle | null = null;
    load()
      .then((module) => {
        const element = ref.current;
        if (cancelled || element === null) return;
        const { aliases = [], ...rest } = latest.current;
        rendered.current = rest.markdown;
        handle = module.mount(element, { ...rest, index: toMdmarkIndex(aliases) });
        setState({
          handle,
          ready: true,
          error: null,
          docId: latest.current.docId,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        logger.error("mdmark_load_failed", { error });
        setState({ handle: null, ready: false, error, docId: null });
      });
    return () => {
      cancelled = true;
      handle?.destroy();
    };
  }, [options.docId, ref]);

  // 同じ文書で本文が変わったら更新する
  const { handle } = state;
  const mounted = state.docId === options.docId;
  useEffect(() => {
    if (!mounted || handle === null || rendered.current === options.markdown)
      return;
    rendered.current = options.markdown;
    handle.update(options.markdown);
  }, [handle, mounted, options.markdown]);

  return { ...state, ready: state.ready && mounted };
};
