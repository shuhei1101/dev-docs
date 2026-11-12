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

/** 描画中の例外の表示。ErrorBoundary とルートの `errorComponent` が使用する。project-index に接続できなかったときは、接続先と理由を出す */
export const ErrorFallback = ({ error, reset }: Props) => {
  useEffect(() => {
    const target = toProjectIndexUnreachable(error);
    if (target) logger.error("project_index_unreachable", target);
    else logger.error("render_failed", { error });
  }, [error]);
  const unreachable = toProjectIndexUnreachable(error);
  const reload = reset ?? (() => location.reload());

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
