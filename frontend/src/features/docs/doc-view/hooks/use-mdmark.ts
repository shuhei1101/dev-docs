import { type RefObject, useEffect, useRef, useState } from "react";

import { logger } from "@/shared/lib/logger";

/** mdmark の読み込み先（採用バージョンのタグを固定した jsDelivr の GitHub の URL） */
export const MDMARK_URL = "https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/mount.js";

export type MdmarkComment = { id: string; quote: string; prefix: string; suffix: string; body: string };

export type MdmarkCommentStore = {
  load: (docId: string) => MdmarkComment[];
  save: (input: {
    docId: string;
    quote: string;
    prefix: string;
    suffix: string;
    body: string;
  }) => MdmarkComment | Promise<MdmarkComment>;
};

export type MdmarkOptions = {
  markdown: string;
  docId: string;
  commentStore: MdmarkCommentStore;
};

export type MdmarkHandle = {
  update: (next: Partial<MdmarkOptions>) => void;
  destroy: () => void;
};

type MdmarkModule = { mount: (element: HTMLElement, options: MdmarkOptions) => MdmarkHandle };

let loading: Promise<MdmarkModule> | null = null;

/** mdmark をモジュールの中で 1 回だけ読む */
const load = (): Promise<MdmarkModule> => {
  loading ??= import(/* @vite-ignore */ MDMARK_URL).catch((error: unknown) => {
    loading = null;
    throw error;
  });
  return loading;
};

type State = { handle: MdmarkHandle | null; ready: boolean; error: unknown };

/** 要素に mdmark で本文を描き、本文の変更で `update`、外れるときに `destroy` する */
export const useMdmark = (
  ref: RefObject<HTMLElement | null>,
  options: MdmarkOptions,
): State => {
  const [state, setState] = useState<State>({ handle: null, ready: false, error: null });
  const latest = useRef(options);
  latest.current = options;
  const rendered = useRef(options.markdown);

  // 文書が変わったら破棄して描き直す
  useEffect(() => {
    let cancelled = false;
    let handle: MdmarkHandle | null = null;
    load()
      .then((module) => {
        const element = ref.current;
        if (cancelled || element === null) return;
        rendered.current = latest.current.markdown;
        handle = module.mount(element, latest.current);
        setState({ handle, ready: true, error: null });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        logger.error("mdmark_load_failed", { error });
        setState({ handle: null, ready: false, error });
      });
    return () => {
      cancelled = true;
      handle?.destroy();
    };
  }, [options.docId, ref]);

  // 同じ文書で本文が変わったら更新する
  const { handle } = state;
  useEffect(() => {
    if (handle === null || rendered.current === options.markdown) return;
    rendered.current = options.markdown;
    handle.update({ markdown: options.markdown });
  }, [handle, options.markdown]);

  return state;
};
