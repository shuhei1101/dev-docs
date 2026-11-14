import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import {
  type SourceFormValues,
  applySource,
  findSource,
  sourceFormSchema,
  sourceKey,
  toFormValues,
} from "@/features/settings/settings/form";
import { toFieldErrors } from "@/features/settings/settings/problem-errors";
import { useSaveSources } from "@/features/settings/settings/queries";
import type { SettingsSourceRow } from "@/shared/api/generated/model";
import {
  AppError,
  ClientValueError,
  VersionConflictError,
} from "@/shared/core/app-error";
import { handleAppError } from "@/shared/core/handle-app-error";

type Options = {
  sources: SettingsSourceRow[];
  /** 開いたときの行の位置（追加は null） */
  index: number | null;
  onSaved: () => void;
};

/** 配信元のダイアログのフォームの状態と保存 */
export const useSourceForm = ({ sources, index, onSaved }: Options) => {
  // 一覧を取得し直して行の位置がずれても同じ配信元を指すよう、開いたときの行を値で持つ
  const [initial] = useState(() => {
    const source = index === null ? null : sources[index];
    return {
      key: source === null ? null : sourceKey(source),
      values: toFormValues(source),
    };
  });
  const targetKey = initial.key;
  const position = targetKey === null ? null : findSource(sources, targetKey);
  const otherIds = sources
    .filter((_, row) => row !== position)
    .flatMap((source) => (source.id ? [source.id] : []));
  const form = useForm<SourceFormValues>({
    resolver: zodResolver(sourceFormSchema(otherIds)),
    defaultValues: initial.values,
    mode: "onSubmit",
    reValidateMode: "onChange",
  });
  // 項目のエラーを描画で参照して購読する
  const { errors } = form.formState;
  const [summary, setSummary] = useState<{ path: string; message: string }[]>(
    [],
  );
  // 開いた後に他のプロセスが端末の設定を変更して、保存を断られたか
  const [conflict, setConflict] = useState(false);
  // 編集していた配信元が他のプロセスに削除されたか
  const gone = position === -1;
  const save = useSaveSources();
  const queryClient = useQueryClient();

  const submit = form.handleSubmit(async (values) => {
    setSummary([]);
    setConflict(false);
    if (gone) return;
    try {
      await save.mutateAsync(applySource(sources, values, position));
      onSaved();
    } catch (error) {
      if (error instanceof VersionConflictError) {
        // 入力を残したまま一覧を最新の内容にし、もう一度保存させる
        setConflict(true);
        await queryClient.invalidateQueries({ refetchType: "all" });
        return;
      }
      if (error instanceof ClientValueError) {
        const { fields, summary: all } = toFieldErrors(
          error.problem?.errors ?? [],
          position ?? sources.length,
        );
        for (const field of fields)
          form.setError(field.name, { message: field.message });
        setSummary(
          all.map((item) => ({ path: item.path, message: item.reason })),
        );
        return;
      }
      const detail =
        error instanceof AppError &&
        (error.status === 502 || error.status === 503)
          ? error.problem?.detail
          : undefined;
      handleAppError(error, {
        message: detail
          ? `端末の設定を保存できませんでした。${detail}`
          : "端末の設定を保存できませんでした。",
      });
    }
  });

  return {
    form,
    errors,
    submit,
    summary,
    conflict,
    gone,
    saving: save.isPending,
  };
};
