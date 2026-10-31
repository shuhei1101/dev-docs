import type { SourceFormValues } from "@/features/settings/settings/form";

type Violation = { path: string; reason: string };

export type FieldError = { name: keyof SourceFormValues; message: string };

const FIELDS: [RegExp, keyof SourceFormValues][] = [
  [/^id$/, "id"],
  [/^config(\[\d+\])*$/, "config"],
  [/^enabled$/, "enabled"],
  [/^scope\.read(\[\d+\])*$/, "read"],
  [/^scope\.write(\[\d+\])*$/, "write"],
];

/** 違反の `path`（`sources[{index}].…`）が指す入力欄を返す。編集・追加した行のものでなければ undefined */
export const fieldOf = (
  path: string,
  index: number,
): keyof SourceFormValues | undefined => {
  const prefix = `sources[${index}].`;
  if (!path.startsWith(prefix)) return undefined;
  const rest = path.slice(prefix.length);
  return FIELDS.find(([pattern]) => pattern.test(rest))?.[1];
};

/** 保存の 422 の `errors[]` のうち、編集・追加した行のものを項目へ、全てをまとめへ振り分ける */
export const toFieldErrors = (
  errors: Violation[],
  index: number,
): { fields: FieldError[]; summary: Violation[] } => {
  const fields: FieldError[] = [];
  for (const error of errors) {
    const name = fieldOf(error.path, index);
    if (name) fields.push({ name, message: error.reason });
  }
  return { fields, summary: errors };
};
