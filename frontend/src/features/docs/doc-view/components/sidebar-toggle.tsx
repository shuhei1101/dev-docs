import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** 画面幅 48rem 以上で、文書の一覧のサイドバーを閉じる・開くボタン */
export const SidebarToggle = ({ open, onOpenChange }: Props) => {
  const label = open ? "サイドバーを閉じる" : "サイドバーを開く";
  const Icon = open ? PanelLeftClose : PanelLeftOpen;
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            aria-label={label}
            aria-expanded={open}
            aria-controls="doc-sidebar"
            onClick={() => onOpenChange(!open)}
          />
        }
      >
        <Icon />
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
};
