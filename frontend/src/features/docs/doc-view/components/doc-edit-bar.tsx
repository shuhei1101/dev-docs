import { Check, FileCode, Pencil, SquarePen } from "lucide-react";

import { usePendingBodyMode } from "@/features/docs/doc-view/edit";
import type { DocEditMode } from "@/features/docs/doc-view/search";
import type { DocumentEdit } from "@/shared/api/generated/model";
import { Button } from "@/shared/components/ui/button";

const MODE_LABEL = { fields: "表示した場所で修正", file: "ファイル全体" } as const satisfies Record<DocEditMode, string>;

type Props = {
  source: string;
  edit: DocumentEdit;
  mode: DocEditMode | undefined;
  onModeChange: (mode: DocEditMode | undefined) => void;
};

/** 文書のタイトルの右の編集のボタンと、編集の方式の切り替え・編集を終了 */
export const DocEditBar = ({ source, edit, mode, onModeChange }: Props) => {
  const pending = usePendingBodyMode(source, edit);
  if (mode === undefined) {
    return (
      <Button variant="outline" size="sm" onClick={() => onModeChange(edit.language === "yaml" ? "fields" : "file")}>
        <Pencil />
        編集
      </Button>
    );
  }
  // 今の方式の変更がある間は、同じ文書の `@file` と項目のパスの変更を並べられないため、もう一方の方式へ切り替えさせない
  const blocked: DocEditMode | null =
    mode === "fields" && pending.fields ? "file" : mode === "file" && pending.file ? "fields" : null;
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap items-center gap-2">
        {edit.language === "yaml" && (
          <div role="group" aria-label="編集の方式" className="flex rounded-md border">
            <Button
              variant={mode === "fields" ? "secondary" : "ghost"}
              size="sm"
              aria-pressed={mode === "fields"}
              disabled={blocked === "fields"}
              onClick={() => onModeChange("fields")}
            >
              <SquarePen />
              {MODE_LABEL.fields}
            </Button>
            <Button
              variant={mode === "file" ? "secondary" : "ghost"}
              size="sm"
              aria-pressed={mode === "file"}
              disabled={blocked === "file"}
              onClick={() => onModeChange("file")}
            >
              <FileCode />
              {MODE_LABEL.file}
            </Button>
          </div>
        )}
        <Button variant="outline" size="sm" onClick={() => onModeChange(undefined)}>
          <Check />
          編集を終了
        </Button>
      </div>
      {blocked !== null && edit.language === "yaml" && (
        <p className="text-xs text-muted-foreground">
          {MODE_LABEL[mode]}の変更をコミットするか元に戻すと切り替えられます。
        </p>
      )}
    </div>
  );
};
