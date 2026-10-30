import { useEffect } from "react";

import { Button } from "@/shared/components/ui/button";
import { logger } from "@/shared/lib/logger";

type Props = {
  error: unknown;
  reset?: () => void;
};

/** 描画中の例外の表示。ErrorBoundary とルートの `errorComponent` が使う */
export const ErrorFallback = ({ error, reset }: Props) => {
  useEffect(() => {
    logger.error("render_failed", { error });
  }, [error]);

  return (
    <div
      role="alert"
      className="mx-auto flex max-w-xl flex-col items-start gap-4 p-8"
    >
      <h1 className="text-lg font-semibold">画面を表示できませんでした。</h1>
      <Button variant="outline" onClick={reset ?? (() => location.reload())}>
        再読み込み
      </Button>
    </div>
  );
};
