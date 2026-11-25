import { CircleAlert } from "lucide-react";
import { useState } from "react";

import { MarkdownPreview } from "@/features/docs/doc-view/components/markdown-preview";
import { type DocEdit, WHOLE_FILE, upsertBodyEdit, usePendingBodyValue } from "@/features/docs/doc-view/edit";
import type { DocumentResponse } from "@/shared/api/generated/model";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
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

type Props = {
  doc: DocumentResponse;
  edit: DocEdit;
};

/** 元のファイルをエディタで書き換え、プレビューと並べる */
export const WholeFileEditor = ({ doc, edit }: Props) => {
  const pending = usePendingBodyValue(doc, WHOLE_FILE);
  const [draft, setDraft] = useState(pending ?? edit.source);
  const errorLine = edit.language === "yaml" ? yamlErrorLine(draft) : null;
  const changed = draft !== (pending ?? edit.source);
  const apply = () =>
    upsertBodyEdit({ doc, edit, path: WHOLE_FILE, label: "ファイル全体", before: edit.source, value: draft });
  return (
    <div className="space-y-3">
      {errorLine !== null && (
        <Alert variant="destructive" role="alert">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>YAML として解析できません</AlertTitle>
          <AlertDescription>{errorLine} 行目の行頭にタブがあります。インデントは空白にしてください。</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="whole-file">{doc.bodyPath ?? doc.path}</Label>
          <Textarea
            id="whole-file"
            value={draft}
            aria-invalid={errorLine !== null}
            className="min-h-96 font-mono text-base md:text-sm"
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
        <section aria-label="プレビュー" className="min-w-0 rounded-md border p-3">
          {edit.language === "markdown" ? (
            <MarkdownPreview markdown={draft} docId={doc.path} />
          ) : (
            <MarkdownPreview markdown={doc.markdown ?? ""} docId={doc.path} />
          )}
        </section>
      </div>
      {changed && (
        <div className="flex gap-2">
          <Button disabled={errorLine !== null} onClick={apply}>
            適用
          </Button>
          <Button variant="outline" onClick={() => setDraft(pending ?? edit.source)}>
            元に戻す
          </Button>
        </div>
      )}
    </div>
  );
};
