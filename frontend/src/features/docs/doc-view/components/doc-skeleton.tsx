import { Skeleton } from "@/shared/components/ui/skeleton";

/** 文書の取得を待つ間の読み込み中の表示（ルートの `pendingComponent`） */
export const DocSkeleton = () => (
  <div
    aria-busy="true"
    aria-label="文書を読み込んでいます"
    className="space-y-4 p-6"
  >
    <Skeleton className="h-8 w-1/3" />
    <Skeleton className="h-4 w-1/2" />
    <Skeleton className="h-64 w-full" />
  </div>
);
