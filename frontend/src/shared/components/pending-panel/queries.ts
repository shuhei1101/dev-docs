import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  getMetadataGetMetadataQueryKey,
  metadataGetMetadata,
  useMetadataPostCommits,
} from "@/shared/api/generated/metadata/metadata";
import type { CommitResult, DocumentEdit, MetadataResponse } from "@/shared/api/generated/model";
import { viewGetDocument } from "@/shared/api/generated/view/view";
import { type AppError, NotFoundError } from "@/shared/core/app-error";
import {
  type EditValue,
  type LatestBodies,
  type LatestValues,
  type PendingEdit,
  toCommitEdits,
  usePendingEditsStore,
} from "@/shared/stores/pending-edits-store";

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

/** 文書の `edit` の項目のパスごとの値（ファイル全体は `@file`）。編集できない文書は空 */
const latestBody = (edit: DocumentEdit | null | undefined): Record<string, EditValue> => {
  if (!edit) return {};
  const blocks = [...edit.blocks, ...(edit.titleBlock ? [edit.titleBlock] : [])];
  return { ...Object.fromEntries(blocks.map((block) => [block.path, block.value])), "@file": edit.source };
};

/** 既定のブランチの先頭の文書を取得する。削除・改名された文書（404）は `null` */
const fetchLatestDocument = async (source: string, path: string) => {
  try {
    return await viewGetDocument(source, path);
  } catch (error) {
    if (error instanceof NotFoundError) return null;
    throw error;
  }
};

export type RestartResult = { dropped: PendingEdit[] };

/** 最新の内容で続ける。既定のブランチの先頭でメタデータと本文の変更の文書を再取得し、編集を始めたときのコミットを置き換え、最新の値と食い違う変更を取り消す */
export const useRestartFromLatest = (source: string) => {
  const queryClient = useQueryClient();
  return useMutation<RestartResult, AppError, void>({
    meta: { handleError: false },
    mutationFn: async () => {
      const edits = usePendingEditsStore.getState().bySource[source] ?? [];
      const bodyEdits = edits.filter((edit) => edit.kind === "body" && edit.docPath !== null);
      const docPaths = [...new Set(bodyEdits.map((edit) => edit.docPath as string))];
      // ref を省き、既定のブランチの先頭で取得する（変更の種類が無い側は取得しない）
      const [metadata, documents] = await Promise.all([
        edits.some((edit) => edit.kind !== "body") ? metadataGetMetadata(source) : Promise.resolve(null),
        Promise.all(docPaths.map((path) => fetchLatestDocument(source, path))),
      ]);
      const bodies: LatestBodies = {};
      for (const edit of bodyEdits) {
        const document = documents[docPaths.indexOf(edit.docPath as string)];
        bodies[edit.docId] = latestBody(document?.edit);
      }
      const baseCommit =
        metadata?.baseCommit ?? documents.find((document) => document?.edit)?.edit?.baseCommit ?? "";
      const dropped = usePendingEditsStore
        .getState()
        .rebase(source, baseCommit, metadata ? latestValues(metadata) : {}, bodies);
      // 記録したコミットで取得する問い合わせの値を、取得した内容にそろえる
      if (metadata?.baseCommit) {
        queryClient.setQueryData(
          getMetadataGetMetadataQueryKey(source, { ref: metadata.baseCommit }),
          metadata,
        );
      }
      // 文書の画面の取得も最新の内容にする
      await queryClient.invalidateQueries({ queryKey: ["view", "document", source] });
      return { dropped };
    },
  });
};
