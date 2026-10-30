import { z } from "zod";

import type {
  SettingsSourceRow as SettingsSource,
  SourceEntry,
} from "@/shared/api/generated/model";

export type SourceFormValues = {
  id: string;
  config: string;
  enabled: boolean;
  read: string;
  write: string;
};

const ID_PATTERN = /^[a-z0-9-]+$/;
const lines = (text: string): string[] =>
  text.split("\n").map((line) => line.trim());
const filled = (text: string): string[] =>
  lines(text).filter((line) => line !== "");

/** 画面設計の入力チェックの表どおりに検証する zod のスキーマを作る */
export const sourceFormSchema = (otherIds: string[]) =>
  z.object({
    id: z.string().superRefine((value, context) => {
      if (value.trim() === "") {
        context.addIssue({
          code: "custom",
          message: "配信元の ID を入力してください。",
        });
      } else if (!ID_PATTERN.test(value)) {
        context.addIssue({
          code: "custom",
          message:
            "配信元の ID に使えない文字があります。英小文字・数字・ハイフンで入力してください。",
        });
      } else if (otherIds.includes(value)) {
        context.addIssue({
          code: "custom",
          message: `配信元の ID ${value} は既に使われています。別の ID を入力してください。`,
        });
      }
    }),
    config: z.string().refine((value) => filled(value).length > 0, {
      message: "設定ファイルを 1 つ以上入力してください。",
    }),
    enabled: z.boolean(),
    read: z
      .string()
      .refine((value) => filled(value).length > 0, {
        message: "読み取りの範囲を 1 つ以上入力してください。",
      })
      .refine((value) => filled(value).length === 0 || !hasBlankLine(value), {
        message: "読み取りの範囲に空の行があります。空の行を削除してください。",
      }),
    write: z.string().refine((value) => !hasBlankLine(value), {
      message: "書き込みの範囲に空の行があります。空の行を削除してください。",
    }),
  });

/** 先頭と末尾の改行を除いた中に空の行があるか */
const hasBlankLine = (text: string): boolean => {
  const trimmed = text.replace(/^\s*\n+|\n+\s*$/g, "");
  return trimmed === "" ? false : lines(trimmed).some((line) => line === "");
};

/** 端末の設定の取得の行（追加のときは null）をダイアログの初期値にする */
export const toFormValues = (
  source: SettingsSource | null,
): SourceFormValues =>
  source === null
    ? { id: "", config: "", enabled: true, read: "", write: "" }
    : {
        id: source.id ?? "",
        config: source.config.join("\n"),
        enabled: source.enabled,
        read: (source.scope.read ?? []).join("\n"),
        write: (source.scope.write ?? []).join("\n"),
      };

/** 取得の行から状態の項目を除き、保存の行にする */
const toSourceInput = (source: SettingsSource): SourceEntry => ({
  ...(source.id ? { id: source.id } : {}),
  config: source.config,
  enabled: source.enabled,
  scope: {
    read: source.scope.read ?? [],
    ...(source.scope.write ? { write: source.scope.write } : {}),
  },
});

const fromValues = (values: SourceFormValues): SourceEntry => {
  const write = filled(values.write);
  return {
    id: values.id,
    config: filled(values.config),
    enabled: values.enabled,
    scope: {
      read: filled(values.read),
      ...(write.length > 0 ? { write } : {}),
    },
  };
};

/** 入力を反映した、端末の設定の保存へ送る `sources[]` を作る（追加は末尾に加える） */
export const applySource = (
  sources: SettingsSource[],
  values: SourceFormValues,
  index: number | null,
): SourceEntry[] => {
  const rows = sources.map(toSourceInput);
  const next = fromValues(values);
  if (index === null) return [...rows, next];
  return rows.map((row, position) => (position === index ? next : row));
};

/** `index` の行を除いた、端末の設定の保存へ送る `sources[]` を作る */
export const removeSource = (
  sources: SettingsSource[],
  index: number,
): SourceEntry[] =>
  sources.filter((_, position) => position !== index).map(toSourceInput);
