import { useEffect, useState } from "react";

/** トップバーと種類のタブの高さ（px） */
const DEFAULT_OFFSET = 96;

/** 目次のリンクで移った見出し(スクロール位置の余白でバーの直下に着く)も、過ぎたものとして数える余白（px） */
const SETTLE_MARGIN = 48;

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
    // スクロールの位置から求めた後は、遅れて届く交差の通知を使わない
    let measured = false;
    const observer = new IntersectionObserver(
      (entries) => {
        if (measured) return;
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).id;
          // 上の線を越えた（上へ出た）見出しを記録し、戻ったら外す
          if (
            !entry.isIntersecting &&
            entry.boundingClientRect.top < offset + SETTLE_MARGIN
          )
            passed.add(id);
          else passed.delete(id);
        }
        const last = [...list].reverse().find((id) => passed.has(id));
        setActive(last ?? null);
      },
      { rootMargin: `-${offset + SETTLE_MARGIN}px 0px 0px 0px` },
    );
    for (const id of list) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    // 目次のリンクなどで見出しを飛び越えたときは交差の変化が起きないため、スクロールのたびに位置から求め直す
    const onScroll = () => {
      measured = true;
      const line = offset + SETTLE_MARGIN;
      const last = list.filter(
        (id) => (document.getElementById(id)?.getBoundingClientRect().top ?? line) < line,
      );
      setActive(last.at(-1) ?? null);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, [key, offset]);

  return active ?? ids[0] ?? null;
};
