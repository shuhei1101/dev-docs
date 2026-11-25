import { useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";

import { SIDEBAR_WIDTH, clampSidebarWidth } from "@/shared/stores/preferences";

/** 矢印キー 1 回で変える幅（CSS px） */
const SIDEBAR_WIDTH_STEP = 16;

type Props = {
  width: number;
  onWidthChange: (width: number) => void;
};

const keyWidth = (key: string, width: number): number | null => {
  switch (key) {
    case "ArrowLeft":
      return width - SIDEBAR_WIDTH_STEP;
    case "ArrowRight":
      return width + SIDEBAR_WIDTH_STEP;
    case "Home":
      return SIDEBAR_WIDTH.min;
    case "End":
      return SIDEBAR_WIDTH.max;
    default:
      return null;
  }
};

/** サイドバーと本文の境目。ドラッグ・矢印キーで幅を変え、ダブルクリックで既定の幅に戻す */
export const SidebarResizer = ({ width, onWidthChange }: Props) => {
  const drag = useRef<{ x: number; width: number } | null>(null);

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    // 押したまま動かしたときに、サイドバーの文字の選択を始めない
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, width };
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current === null) return;
    onWidthChange(
      clampSidebarWidth(drag.current.width + event.clientX - drag.current.x),
    );
  };
  const onPointerEnd = () => {
    drag.current = null;
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = keyWidth(event.key, width);
    if (next === null) return;
    event.preventDefault();
    onWidthChange(clampSidebarWidth(next));
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="サイドバーの幅"
      aria-valuenow={width}
      aria-valuemin={SIDEBAR_WIDTH.min}
      aria-valuemax={SIDEBAR_WIDTH.max}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- 値を持つ separator はフォーカスして矢印キーで動かす操作部品（WAI-ARIA の Window Splitter）
      tabIndex={0}
      title="ドラッグで幅を変更（ダブルクリックで既定の幅）"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd}
      onPointerCancel={onPointerEnd}
      onDoubleClick={() => onWidthChange(SIDEBAR_WIDTH.initial)}
      onKeyDown={onKeyDown}
      className="group flex w-3 shrink-0 cursor-col-resize touch-none justify-center self-stretch outline-none"
    >
      <span className="h-full w-px bg-border transition-colors group-hover:bg-primary group-focus-visible:w-0.5 group-focus-visible:bg-ring group-active:bg-primary motion-reduce:transition-none" />
    </div>
  );
};
