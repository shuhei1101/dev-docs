import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  getMetadataGetMetadataQueryKey,
  metadataGetMetadata,
  useMetadataPostCommits,
} from "@/shared/api/generated/metadata/metadata";
import type { CommitResult, MetadataResponse } from "@/shared/api/generated/model";
import type { AppError } from "@/shared/core/app-error";
import {
  type LatestValues,
  type PendingEdit,
  toCommitEdits,
  usePendingEditsStore,
} from "@/features/metadata/shared/pending-edits-store";

export type CommitVariables = { dryRun: boolean; message?: string };

/** 編集中の変更の直コミット。コミットした後（衝突してブランチに残した後も）に編集中の変更を空にし、メタデータと文書を再取得する */
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
  const mutateAsync = ({ dryRun, message }: CommitVariables): Promise<CommitResult> => {
    const state = usePendingEditsStore.getState();
    return mutation.mutateAsync({
      source,
      data: {
        edits: toCommitEdits(state.bySource[source] ?? []),
        // 編集を始めたときのコミット（衝突したときのブランチの起点）
        baseCommit: state.baseCommitBySource[source] ?? "",
        dryRun,
        ...(dryRun || message === undefined ? {} : { message }),
      },
    });
  };
  return { ...mutation, mutateAsync };
};

/** メタデータの種類・行の ID ごとの値 */
const latestValues = (metadata: MetadataResponse): LatestValues =>
  Object.fromEntries(
    metadata.kinds.map((kind) => [
      kind.id,
      Object.fromEntries(kind.rows.map((row) => [row.id, row.values])),
    ]),
  );

export type RestartResult = { metadata: MetadataResponse; dropped: PendingEdit[] };

/** 最新の内容で続ける。既定のブランチの先頭でメタデータを再取得し、編集を始めたときのコミットを置き換え、最新の値と食い違う変更を取り消す */
export const useRestartFromLatest = (source: string) => {
  const queryClient = useQueryClient();
  return useMutation<RestartResult, AppError, void>({
    meta: { handleError: false },
    mutationFn: async () => {
      // ref を省き、既定のブランチの先頭で取得する
      const metadata = await metadataGetMetadata(source);
      const dropped = usePendingEditsStore
        .getState()
        .rebase(source, metadata.baseCommit ?? "", latestValues(metadata));
      // 記録したコミットで取得する問い合わせの値を、取得した内容にそろえる
      if (metadata.baseCommit) {
        queryClient.setQueryData(
          getMetadataGetMetadataQueryKey(source, { ref: metadata.baseCommit }),
          metadata,
        );
      }
      return { metadata, dropped };
    },
  });
};
