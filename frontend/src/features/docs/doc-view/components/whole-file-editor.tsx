import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";
import { useDeferredValue } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import {
  type DocEdit,
  WHOLE_FILE,
  previewQueryOptions,
  upsertBodyEdit,
  usePendingBodyValue,
} from "@/features/docs/doc-view/edit";
import type { DocumentResponse } from "@/shared/api/generated/model";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

/** 行頭のタブ（YAML として解析できない書き換えの例） */
const TAB_INDENT = /^\t/m;

/** YAML として解析できない書き換えの行番号（解析できるなら null） */
const yamlErrorLine = (text: string): number | null => {
  const match = TAB_INDENT.exec(text);
  return match === null ? null : text.slice(0, match.index).split("\n").length;
};

type PreviewProps = { doc: DocumentResponse; content: string; enabled: boolean };

/** 書き換えた YAML を変換したプレビュー（解析できない間は最後に変換できた内容） */
const YamlPreview = ({ doc, content, enabled }: PreviewProps) => {
  const preview = useQuery({ ...previewQueryOptions(doc, content), enabled });
  return <MarkdownPreview markdown={preview.data?.markdown ?? doc.markdown ?? ""} docId={doc.path} />;
};

type Props = {
  doc: DocumentResponse;
  edit: DocEdit;
};

/** 元のファイルをエディタで書き換え、プレビューと並べる。書き換えはその場で編集中の変更に入れる */
export const WholeFileEditor = ({ doc, edit }: Props) => {
  const pending = usePendingBodyValue(doc, WHOLE_FILE);
  const draft = pending ?? edit.source;
  const deferred = useDeferredValue(draft);
  const errorLine = edit.language === "yaml" ? yamlErrorLine(draft) : null;
  const set = (value: string) =>
    upsertBodyEdit({ doc, edit, path: WHOLE_FILE, label: "ファイル全体", before: edit.source, value });
  return (
    <div className="@container space-y-3">
      {errorLine !== null && (
        <Alert variant="destructive" role="alert">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>YAML として解析できません</AlertTitle>
          <AlertDescription>
            {errorLine} 行目の行頭にタブがあります。インデントは空白にしてください。このままでは差分確認とコミットで断られます。
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 @3xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex min-h-6 items-center gap-2">
            <Label htmlFor="whole-file" className="min-w-0 wrap-anywhere">
              {doc.bodyPath ?? doc.path}
            </Label>
            {pending !== undefined && (
              <>
                <Badge variant="outline" className="shrink-0">
                  変更あり
                </Badge>
                <Button variant="ghost" size="sm" className="ml-auto shrink-0" onClick={() => set(edit.source)}>
                  元に戻す
                </Button>
              </>
            )}
          </div>
          <Textarea
            id="whole-file"
            value={draft}
            aria-invalid={errorLine !== null}
            className="min-h-96 font-mono text-base md:text-sm"
            onChange={(event) => set(event.target.value)}
          />
        </div>
        <section aria-label="プレビュー" className="min-w-0 rounded-md border p-3">
          {edit.language === "markdown" ? (
            <MarkdownPreview markdown={deferred} docId={doc.path} />
          ) : (
            <YamlPreview doc={doc} content={deferred} enabled={yamlErrorLine(deferred) === null} />
          )}
        </section>
      </div>
    </div>
  );
};
