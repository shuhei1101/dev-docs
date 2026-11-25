import { Check, FileCode, Pencil, SquarePen } from "lucide-react";

import type { DocEdit } from "@/features/docs/doc-view/edit";
import type { DocEditMode } from "@/features/docs/doc-view/search";
import { Button } from "@/shared/components/ui/button";

type Props = {
  edit: DocEdit | null;
  mode: DocEditMode | undefined;
  onModeChange: (mode: DocEditMode | undefined) => void;
};

/** 文書のヘッダーの編集のボタンと、編集中の表示の切り替え */
export const DocEditBar = ({ edit, mode, onModeChange }: Props) => {
  if (edit === null || !edit.editable) return null;
  if (mode === undefined) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => onModeChange(edit.language === "yaml" ? "fields" : "file")}
      >
        <Pencil />
        編集
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {edit.language === "yaml" && (
        <div role="group" aria-label="編集の方式" className="flex rounded-md border">
          <Button
            variant={mode === "fields" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={mode === "fields"}
            onClick={() => onModeChange("fields")}
          >
            <SquarePen />
            表示した場所で修正
          </Button>
          <Button
            variant={mode === "file" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={mode === "file"}
            onClick={() => onModeChange("file")}
          >
            <FileCode />
            ファイル全体
          </Button>
        </div>
      )}
      <Button variant="outline" size="sm" onClick={() => onModeChange(undefined)}>
        <Check />
        編集を終了
      </Button>
    </div>
  );
};
