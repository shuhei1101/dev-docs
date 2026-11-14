import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { useSaveSources } from "@/features/settings/settings/queries";
import {
  findSource,
  removeSource,
  sourceKey,
} from "@/features/settings/settings/form";
import type { SettingsSourceRow } from "@/shared/api/generated/model";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { AppError, VersionConflictError } from "@/shared/core/app-error";
import { handleAppError } from "@/shared/core/handle-app-error";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: SettingsSourceRow[];
  index: number;
};

const folderOf = (file: string | undefined): string =>
  file === undefined ? "" : file.slice(0, Math.max(file.lastIndexOf("/"), 0));

/** 削除の確認のダイアログ。確定で、その行を除いた `sources[]` を保存する */
export const SourceDeleteDialog = ({
  open,
  onOpenChange,
  sources,
  index,
}: Props) => {
  const save = useSaveSources();
  const queryClient = useQueryClient();
  const [failure, setFailure] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  // 一覧を取得し直して行の位置がずれても同じ配信元を指すよう、開いたときの行を値で持つ
  const [target] = useState(() => {
    const source = sources[index];
    return {
      key: source === undefined ? null : sourceKey(source),
      name: source?.id ?? `${index + 1} 行目`,
      folder: folderOf(source?.config[0]),
    };
  });
  const position = target.key === null ? -1 : findSource(sources, target.key);
  // 削除する配信元が他のプロセスに削除されたか
  const gone = position === -1;

  const remove = async () => {
    setFailure(null);
    setConflict(false);
    if (gone) return;
    try {
      await save.mutateAsync(removeSource(sources, position));
      onOpenChange(false);
    } catch (error) {
      if (error instanceof VersionConflictError) {
        // 一覧を最新の内容にし、確認してからもう一度削除させる
        setConflict(true);
        await queryClient.invalidateQueries({ refetchType: "all" });
        return;
      }
      setFailure(
        error instanceof AppError
          ? (error.problem?.detail ?? error.message)
          : "端末の設定を保存できませんでした。",
      );
      handleAppError(error, { message: "端末の設定を保存できませんでした。" });
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent initialFocus={cancelRef}>
        <AlertDialogHeader>
          <AlertDialogTitle>{target.name} を削除しますか?</AlertDialogTitle>
          <AlertDialogDescription>
            端末の設定から {target.name}{" "}
            の行を削除し、配信から除外します。フォルダ {target.folder}{" "}
            と文書は削除しません。
          </AlertDialogDescription>
        </AlertDialogHeader>
        {gone && (
          <Alert role="alert">
            <AlertTitle>配信元が削除されたため削除できませんでした</AlertTitle>
            <AlertDescription>
              この画面を開いた後に、他のプロセスがこの配信元を端末の設定から削除しました。一覧を確認してください。
            </AlertDescription>
          </Alert>
        )}
        {conflict && !gone && (
          <Alert role="alert">
            <AlertTitle>他の変更があったため削除できませんでした</AlertTitle>
            <AlertDescription>
              この画面を開いた後に、他のプロセスが端末の設定を変更しました。一覧を最新の内容にしました。内容を確認し、もう一度削除してください。
            </AlertDescription>
          </Alert>
        )}
        {failure !== null && <Alert variant="destructive">{failure}</Alert>}
        <AlertDialogFooter>
          <AlertDialogCancel ref={cancelRef}>キャンセル</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={save.isPending || gone}
            onClick={(event) => {
              event.preventDefault();
              void remove();
            }}
          >
            削除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
