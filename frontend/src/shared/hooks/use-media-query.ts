import { useSyncExternalStore } from "react";

/** CSS のメディアクエリに今当たっているかを返す(画面幅の変化にも追従する) */
export const useMediaQuery = (query: string): boolean =>
  useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
