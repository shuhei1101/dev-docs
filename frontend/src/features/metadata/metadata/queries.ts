import { useQueryClient } from "@tanstack/react-query";

import {
  getMetadataGetMetadataQueryKey,
  useMetadataPostCommits,
} from "@/shared/api/generated/metadata/metadata";
import type { CommitResult } from "@/shared/api/generated/model";
import type { AppError } from "@/shared/core/app-error";
import {
  toCommitEdits,
  usePendingEditsStore,
} from "@/features/metadata/shared/pending-edits-store";

export type CommitVariables = { dryRun: boolean; message?: string };

/** 編集中の変更の直コミット。コミットした後に編集中の変更を空にし、メタデータと文書を再取得する */
export const useCommitEdits = (source: string) => {
  const queryClient = useQueryClient();
  const mutation = useMetadataPostCommits<AppError>({
    mutation: {
      // 失敗はパネルが変更ごとの理由として出す
      meta: { handleError: false },
      onSuccess: async (_result, variables) => {
        if (variables.data.dryRun) return;
        usePendingEditsStore.getState().clear(source);
        await queryClient.invalidateQueries({
          queryKey: getMetadataGetMetadataQueryKey(source),
          refetchType: "all",
        });
        // 文書の画面の取得も古くなる
        await queryClient.invalidateQueries({ queryKey: ["view", "document", source] });
      },
    },
  });
  const mutateAsync = ({ dryRun, message }: CommitVariables): Promise<CommitResult> =>
    mutation.mutateAsync({
      source,
      data: {
        edits: toCommitEdits(usePendingEditsStore.getState().bySource[source] ?? []),
        dryRun,
        ...(dryRun || message === undefined ? {} : { message }),
      },
    });
  return { ...mutation, mutateAsync };
};
