import { useEffect, useState } from "react";

/** トップバーと種類のタブの高さ（px） */
const DEFAULT_OFFSET = 96;

/** 渡した見出しの ID のうち、画面の一番上を過ぎた最後の見出しを返す */
export const useActiveHeading = (
  ids: string[],
  offset: number = DEFAULT_OFFSET,
): string | null => {
  const [active, setActive] = useState<string | null>(null);
  const key = ids.join("\n");

  useEffect(() => {
    const list = key === "" ? [] : key.split("\n");
    const passed = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).id;
          // 上の線を越えた（上へ出た）見出しを記録し、戻ったら外す
          if (!entry.isIntersecting && entry.boundingClientRect.top < offset)
            passed.add(id);
          else passed.delete(id);
        }
        const last = [...list].reverse().find((id) => passed.has(id));
        setActive(last ?? null);
      },
      { rootMargin: `-${offset}px 0px 0px 0px` },
    );
    for (const id of list) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [key, offset]);

  return active ?? ids[0] ?? null;
};
