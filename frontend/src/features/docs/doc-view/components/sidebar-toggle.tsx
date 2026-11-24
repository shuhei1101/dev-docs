import type { LucideIcon } from "lucide-react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

type IconButtonProps = {
  label: string;
  Icon: LucideIcon;
  onClick: () => void;
  expanded?: boolean;
};

/** アイコンだけのボタン。ホバーとフォーカスでラベルのツールチップを出す */
const IconButton = ({
  label,
  Icon,
  onClick,
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
          aria-controls={expanded === true ? "doc-sidebar" : undefined}
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
