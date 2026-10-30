import { useRef, useState } from "react";

import { useSaveSources } from "@/features/settings/settings/queries";
import { removeSource } from "@/features/settings/settings/form";
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
import { Alert } from "@/shared/components/ui/alert";
import { AppError } from "@/shared/core/app-error";
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
  const [failure, setFailure] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const source = sources[index];
  const name = source?.id ?? `${index + 1} 行目`;

  const remove = async () => {
    setFailure(null);
    try {
      await save.mutateAsync(removeSource(sources, index));
      onOpenChange(false);
    } catch (error) {
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
          <AlertDialogTitle>{name} を削除しますか?</AlertDialogTitle>
          <AlertDialogDescription>
            端末の設定から {name} の行を削除し、配信から外します。フォルダ{" "}
            {folderOf(source?.config[0])} と文書は削除しません。
          </AlertDialogDescription>
        </AlertDialogHeader>
        {failure !== null && <Alert variant="destructive">{failure}</Alert>}
        <AlertDialogFooter>
          <AlertDialogCancel ref={cancelRef}>キャンセル</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={save.isPending}
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
