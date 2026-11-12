import { useEffect } from "react";

import {
  ProjectIndexUnreachableAlert,
  toProjectIndexUnreachable,
} from "@/shared/components/project-index-unreachable";
import { Button } from "@/shared/components/ui/button";
import { logger } from "@/shared/lib/logger";

type Props = {
  error: unknown;
  reset?: () => void;
};

/** 描画中の例外の表示。ErrorBoundary とルートの `errorComponent` が使う。project-index に接続できなかったときは、接続先と理由を出す */
export const ErrorFallback = ({ error, reset }: Props) => {
  useEffect(() => {
    logger.error("render_failed", { error });
  }, [error]);
  const reload = reset ?? (() => location.reload());
  const unreachable = toProjectIndexUnreachable(error);

  if (unreachable) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <ProjectIndexUnreachableAlert {...unreachable} onReload={reload} />
      </div>
    );
  }
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-xl flex-col items-start gap-4 p-8"
    >
      <h1 className="text-lg font-semibold">画面を表示できませんでした。</h1>
      <Button variant="outline" onClick={reload}>
        再読み込み
      </Button>
    </div>
  );
};
