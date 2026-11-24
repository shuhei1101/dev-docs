import type { LucideIcon } from "lucide-react";
import {
  FoldHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  UnfoldHorizontal,
} from "lucide-react";

import { SIDEBAR_WIDTH_STEP } from "@/features/docs/doc-view/components/sidebar-resizer";
import { Button } from "@/shared/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { SIDEBAR_WIDTH } from "@/shared/stores/preferences";

type IconButtonProps = {
  label: string;
  Icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  expanded?: boolean;
};

/** アイコンだけのボタン。ホバーとフォーカスでラベルのツールチップを出す */
const IconButton = ({
  label,
  Icon,
  onClick,
  disabled,
  expanded,
}: IconButtonProps) => (
  <Tooltip>
    <TooltipTrigger
      render={
        <Button
          variant="ghost"
          size="icon"
          aria-label={label}
          aria-expanded={expanded}
          aria-controls={expanded === undefined ? undefined : "doc-sidebar"}
          disabled={disabled}
          onClick={onClick}
        />
      }
    >
      <Icon />
    </TooltipTrigger>
    <TooltipContent side="bottom">{label}</TooltipContent>
  </Tooltip>
);

type ToggleProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** 画面幅 48rem 以上で、文書の一覧のサイドバーを閉じる・開くボタン */
export const SidebarToggle = ({ open, onOpenChange }: ToggleProps) => (
  <IconButton
    label={open ? "サイドバーを閉じる" : "サイドバーを開く"}
    Icon={open ? PanelLeftClose : PanelLeftOpen}
    expanded={open}
    onClick={() => onOpenChange(!open)}
  />
);

type WidthProps = {
  width: number;
  onWidthChange: (width: number) => void;
};

/** サイドバーの幅を一定の量ずつ狭める・広げるボタン（境目をドラッグしない代わりの手段） */
export const SidebarWidthButtons = ({ width, onWidthChange }: WidthProps) => (
  <>
    <IconButton
      label="サイドバーを狭める"
      Icon={FoldHorizontal}
      disabled={width <= SIDEBAR_WIDTH.min}
      onClick={() => onWidthChange(width - SIDEBAR_WIDTH_STEP)}
    />
    <IconButton
      label="サイドバーを広げる"
      Icon={UnfoldHorizontal}
      disabled={width >= SIDEBAR_WIDTH.max}
      onClick={() => onWidthChange(width + SIDEBAR_WIDTH_STEP)}
    />
  </>
);
