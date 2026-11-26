import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import {
  PREVIEW_DELAY_MS,
  WHOLE_FILE,
  bodyEditKey,
  previewQueryOptions,
  upsertBodyEdit,
  usePendingBodyValue,
} from "@/features/docs/doc-view/edit";
import type { ConversionError, DocumentEdit } from "@/shared/api/generated/model";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import { usePendingEditsStore } from "@/shared/stores/pending-edits-store";

/** 値が `delayMs` 変わらなかったときの値（入力が止まった後に問い合わせる） */
const useSettledValue = (value: string, delayMs: number): string => {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return settled;
};

type PreviewProps = {
  source: string;
  path: string;
  docId: string;
  initial: string;
  content: string;
  /** 元の内容から書き換えたか（書き換えていない間は文書の取得の `markdown` を出す） */
  enabled: boolean;
  onError: (error: ConversionError | null) => void;
};

/** 書き換えた YAML を変換したプレビュー（変換できない間は最後に変換できた内容） */
const YamlPreview = ({ source, path, docId, initial, content, enabled, onError }: PreviewProps) => {
  const preview = useQuery({ ...previewQueryOptions(source, path, content), enabled });
  const [last, setLast] = useState(initial);
  const next = enabled ? preview.data?.markdown : initial;
  // 変換できた応答: 最後に変換できた内容を更新する（描画の中で前の値から求める）
  if (next !== undefined && next !== null && next !== last) setLast(next);
  const error = enabled ? (preview.data?.conversionError ?? null) : null;
  useEffect(() => onError(error), [error, onError]);
  return (
    <>
      {enabled && preview.data?.fallback && (
        <p className="mb-2 text-xs text-muted-foreground">
          この種類のプレビューは、配信元の変換を使用できないため標準の変換で表示しています。
        </p>
      )}
      <MarkdownPreview markdown={last} docId={docId} />
    </>
  );
};

type Props = {
  source: string;
  /** 文書の取得の `path` */
  path: string;
  /** mdmark の `docId`（`{source}@{ref}:{path}`） */
  docId: string;
  /** 文書の取得の `markdown`（プレビューの最初の内容） */
  markdown: string | null;
  edit: DocumentEdit;
};

/** 元のファイルをエディタで書き換え、プレビューと並べる。書き換えはその場で編集中の変更に入れる */
export const WholeFileEditor = ({ source, path, docId, markdown, edit }: Props) => {
  const pending = usePendingBodyValue(source, edit, WHOLE_FILE);
  const draft = typeof pending === "string" ? pending : edit.source;
  const deferred = useDeferredValue(draft);
  const settled = useSettledValue(draft, PREVIEW_DELAY_MS);
  const [error, setError] = useState<ConversionError | null>(null);
  const invalid = edit.language === "yaml" && error !== null;
  const set = (value: string) =>
    upsertBodyEdit(source, edit, { path: WHOLE_FILE, label: "ファイル全体", before: edit.source, value });
  const revert = () => usePendingEditsStore.getState().remove(source, bodyEditKey(edit, WHOLE_FILE));
  return (
    <div className="@container space-y-3">
      {invalid && (
        <Alert variant="destructive" role="alert">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>YAML として解析できません</AlertTitle>
          <AlertDescription>
            {error.line} 行 {error.column} 列: {error.detail}。このままでは差分確認とコミットでエラーが発生します。
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 @3xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex min-h-6 items-center gap-2">
            <Label htmlFor="whole-file" className="min-w-0 wrap-anywhere">
              {edit.filePath}
            </Label>
            {pending !== undefined && (
              <>
                <Badge variant="outline" className="shrink-0">
                  変更あり
                </Badge>
                <Button variant="ghost" size="sm" className="ml-auto shrink-0" onClick={revert}>
                  元に戻す
                </Button>
              </>
            )}
          </div>
          <Textarea
            id="whole-file"
            value={draft}
            aria-invalid={invalid}
            className="min-h-96 font-mono text-base md:text-sm"
            onChange={(event) => set(event.target.value)}
          />
        </div>
        <section aria-label="プレビュー" className="min-w-0 rounded-md border p-3">
          {edit.language === "markdown" ? (
            <MarkdownPreview markdown={deferred} docId={docId} />
          ) : (
            <YamlPreview
              source={source}
              path={path}
              docId={docId}
              initial={markdown ?? ""}
              content={settled}
              enabled={settled !== edit.source}
              onError={setError}
            />
          )}
        </section>
      </div>
    </div>
  );
};
