import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import {
  type SourceFormValues,
  applySource,
  sourceFormSchema,
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
  index: number | null;
  onSaved: () => void;
};

/** 配信元のダイアログのフォームの状態と保存 */
export const useSourceForm = ({ sources, index, onSaved }: Options) => {
  const otherIds = sources
    .filter((_, position) => position !== index)
    .flatMap((source) => (source.id ? [source.id] : []));
  const form = useForm<SourceFormValues>({
    resolver: zodResolver(sourceFormSchema(otherIds)),
    defaultValues: toFormValues(index === null ? null : sources[index]),
    mode: "onSubmit",
    reValidateMode: "onChange",
  });
  // 項目のエラーを描画で参照して購読する
  const { errors } = form.formState;
  const [summary, setSummary] = useState<{ path: string; message: string }[]>(
    [],
  );
  // 開いた後にほかのプロセスが端末の設定を変更して、保存を断られたか
  const [conflict, setConflict] = useState(false);
  const save = useSaveSources();
  const queryClient = useQueryClient();

  const submit = form.handleSubmit(async (values) => {
    setSummary([]);
    setConflict(false);
    try {
      await save.mutateAsync(applySource(sources, values, index));
      onSaved();
    } catch (error) {
      if (error instanceof VersionConflictError) {
        // 入力を残したまま一覧を最新の内容にし、もう一度保存させる
        setConflict(true);
        await queryClient.invalidateQueries({ refetchType: "all" });
        return;
      }
      if (error instanceof ClientValueError) {
        const position = index ?? sources.length;
        const { fields, summary: all } = toFieldErrors(
          error.problem?.errors ?? [],
          position,
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
    saving: save.isPending,
  };
};
