import { type AnyRouter, useRouterState } from "@tanstack/react-router";

import { INITIAL_LOADING_MS } from "@/app/pending";
import { DocSkeleton } from "@/features/docs/doc-view/components/doc-skeleton";
import { useDelayedFlag } from "@/shared/hooks/use-delayed-flag";

type Props = { router: AnyRouter };

/** 最初の画面の読み込みが 1 秒を超えたときだけ、読み込み中の表示を出す(画面の移動では前の画面を出したままにする) */
export const InitialLoading = ({ router }: Props) => {
  const initial = useRouterState({
    router,
    select: (state) => state.resolvedLocation === undefined,
  });
  const waiting = useDelayedFlag(initial, INITIAL_LOADING_MS);
  return waiting ? <DocSkeleton /> : null;
};
