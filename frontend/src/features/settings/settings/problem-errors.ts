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

/** 保存の 422 の `errors[]` のうち、編集・追加した行のものを項目へ、全てをまとめへ振り分ける */
export const toFieldErrors = (
  errors: Violation[],
  index: number,
): { fields: FieldError[]; summary: Violation[] } => {
  const prefix = `sources[${index}].`;
  const fields: FieldError[] = [];
  for (const error of errors) {
    if (!error.path.startsWith(prefix)) continue;
    const rest = error.path.slice(prefix.length);
    const name = FIELDS.find(([pattern]) => pattern.test(rest))?.[1];
    if (name) fields.push({ name, message: error.reason });
  }
  return { fields, summary: errors };
};
