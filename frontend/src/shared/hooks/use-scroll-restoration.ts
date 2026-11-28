import { type RefObject, useEffect, useRef } from "react";

/** スクロールの間に `sessionStorage` へ書き込む間隔（ミリ秒） */
export const SCROLL_SAVE_INTERVAL_MS = 200;

const readPosition = (key: string): number => {
  const value = Number(sessionStorage.getItem(key));
  return Number.isFinite(value) ? value : 0;
};

/** 要素の縦のスクロール位置をキーごとに `sessionStorage` に保存し、キーが変わったときに新しいキーの位置へ戻す */
export const useScrollRestoration = (
  ref: RefObject<HTMLElement | null>,
  key: string,
): void => {
  const previousKey = useRef<string | null>(null);

  // キーが変わったときだけ、ルーターの復元の後のフレームで新しいキーの位置へ戻す
  useEffect(() => {
    const previous = previousKey.current;
    previousKey.current = key;
    if (previous === null || previous === key) return;
    const frame = requestAnimationFrame(() => {
      const element = ref.current;
      if (element !== null) element.scrollTop = readPosition(key);
    });
    return () => window.cancelAnimationFrame?.(frame);
  }, [ref, key]);

  // スクロールを間引いて保存し、キーが変わる前と pagehide でその時点の位置を保存する
  useEffect(() => {
    const element = ref.current;
    if (element === null) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const save = () => {
      sessionStorage.setItem(key, String(element.scrollTop));
    };
    const onScroll = () => {
      if (timer !== null) return;
      timer = setTimeout(() => {
        timer = null;
        save();
      }, SCROLL_SAVE_INTERVAL_MS);
    };
    element.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pagehide", save);
    return () => {
      if (timer !== null) clearTimeout(timer);
      save();
      element.removeEventListener("scroll", onScroll);
      window.removeEventListener("pagehide", save);
    };
  }, [ref, key]);
};
