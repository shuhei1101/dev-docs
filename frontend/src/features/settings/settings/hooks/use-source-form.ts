import { zodResolver } from "@hookform/resolvers/zod";
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
import { ClientValueError } from "@/shared/core/app-error";
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
  // 項目のエラーを描画で読んで購読する
  const { errors } = form.formState;
  const [summary, setSummary] = useState<{ path: string; message: string }[]>(
    [],
  );
  const save = useSaveSources();

  const submit = form.handleSubmit(async (values) => {
    setSummary([]);
    try {
      await save.mutateAsync(applySource(sources, values, index));
      onSaved();
    } catch (error) {
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
      handleAppError(error, { message: "端末の設定を保存できませんでした。" });
    }
  });

  return { form, errors, submit, summary, saving: save.isPending };
};
