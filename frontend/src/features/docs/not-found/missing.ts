import { MissingSchema } from "@/shared/core/schema";

export type MissingKind = "source" | "not_served" | "ref" | "doc" | "route";

export type MissingDescription = {
  kind: MissingKind;
  heading: string;
  description: string;
  details: { label: string; value: string }[];
};

export type MissingContext = {
  /** リビジョンの一覧の `defaultRef` */
  defaultRef?: string;
  /** 端末の設定の取得のその配信元の `config` */
  configs?: string[];
  /** URL の配信元の ID と開こうとしたリビジョン（説明の文言に入れる） */
  source?: string;
  ref?: string;
};

/** 文書の取得の 404 の `missing` を、見出し・説明・詳細の行にする */
export const describeMissing = (
  data: unknown,
  context: MissingContext = {},
): MissingDescription => {
  const parsed = MissingSchema.safeParse(data);
  if (!parsed.success) {
    return {
      kind: "route",
      heading: "ページが見つかりません",
      description: "この URL に当たる画面はありません。",
      details: [],
    };
  }
  const { missing, value, errors } = parsed.data;
  const source = context.source ?? "";
  switch (missing) {
    case "doc":
      return {
        kind: "doc",
        heading: "文書が見つかりません",
        description: context.ref
          ? `配信元 ${source} のリビジョン ${context.ref} に、この文書はありません。`
          : `配信元 ${source} に、この文書はありません。`,
        details: [{ label: "開こうとしたパス", value }],
      };
    case "ref":
      return {
        kind: "ref",
        heading: "リビジョンが見つかりません",
        description: `配信元 ${source} に、リビジョン ${value} はありません。`,
        details: [
          { label: "開こうとしたリビジョン", value },
          ...(context.defaultRef
            ? [{ label: "既定のリビジョン", value: context.defaultRef }]
            : []),
        ],
      };
    case "not_served":
      return {
        kind: "not_served",
        heading: `配信元 ${value} を配信していません`,
        description: "起動時の検証で、配信から外しました。",
        details: [
          ...(errors ?? []).map((error) => ({
            label: "外した理由",
            value: `${error.path} ${error.reason}`,
          })),
          ...(context.configs ?? []).map((config) => ({
            label: "設定ファイル",
            value: config,
          })),
        ],
      };
    case "source":
      return {
        kind: "source",
        heading: `配信元 ${value} はありません`,
        description: "端末の設定に、この ID の配信元はありません。",
        details: [],
      };
  }
};
