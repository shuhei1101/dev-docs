import type { ReactNode } from "react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
};

/** 狭い幅で文書の一覧を重ねて出すドロワー */
export const SidebarDrawer = ({ open, onOpenChange, children }: Props) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="left" className="w-72">
      <SheetHeader>
        <SheetTitle>文書の一覧</SheetTitle>
      </SheetHeader>
      <div className="overflow-y-auto px-4 pb-4">{children}</div>
    </SheetContent>
  </Sheet>
);
