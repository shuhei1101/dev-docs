import { Skeleton } from "@/shared/components/ui/skeleton";

/** 端末の設定の取得を待つ間に出す、表の行の形の枠 */
export const SourceSkeleton = () => (
  <div
    aria-busy="true"
    aria-label="配信元を読み込んでいます"
    className="space-y-2"
  >
    <Skeleton className="h-9 w-full" />
    <Skeleton className="h-9 w-full" />
    <Skeleton className="h-9 w-full" />
  </div>
);
