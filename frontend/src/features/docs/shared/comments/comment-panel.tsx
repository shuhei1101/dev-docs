import { Pencil, Trash2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { buildIssueUrl, formatComments } from "@/features/docs/shared/comments/comment-format";
import { type DocComment, useCommentStore } from "@/features/docs/shared/comments/comment-store";
import type { GitHubTarget } from "@/shared/api/generated/model";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/shared/components/ui/sheet";
import { Textarea } from "@/shared/components/ui/textarea";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  github: GitHubTarget | null;
  onLocate: (comment: DocComment) => void;
  onChanged: () => void;
};

const placeOf = (comment: DocComment): string =>
  [comment.docTitle, ...(comment.headings.length > 0 ? comment.headings : ["冒頭"])].join(" › ");

/** 溜めたコメントの一覧と、コピー・起票 */
export const CommentPanel = ({ open, onOpenChange, github, onLocate, onChanged }: Props) => {
  const { comments, setSelected, update, remove } = useCommentStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);

  const chosen = comments.filter((comment) => comment.selected);
  const all = comments.length > 0 && chosen.length === comments.length;
  const mixed = chosen.length > 0 && !all;

  const copy = async (text: string): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      toast.error("クリップボードにコピーできませんでした。");
      return false;
    }
  };

  const onCopy = async () => {
    if (await copy(formatComments(chosen))) {
      toast.success(`選択 ${chosen.length} 件をクリップボードにコピーしました。`);
    }
  };

  const onIssue = async () => {
    if (github === null) return;
    const body = formatComments(chosen);
    if (!(await copy(body))) return;
    const { url, truncated } = buildIssueUrl(github, body);
    window.open(url, "_blank", "noopener");
    toast.success("Issue の作成画面を別のタブで開きました。");
    if (truncated) toast.success("本文が長いため末尾を切り詰め、全文をクリップボードにコピーしました。");
  };

  const startEdit = (comment: DocComment) => {
    setEditingId(comment.id);
    setDraft(comment.body);
    setInvalid(false);
  };

  const save = () => {
    if (draft.trim() === "") {
      setInvalid(true);
      return;
    }
    if (editingId !== null) update(editingId, draft);
    setEditingId(null);
    onChanged();
  };

  return (
    <Sheet modal={false} open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" showCloseButton={false} className="w-96 max-w-full">
        <SheetHeader className="flex-row items-center justify-between">
          <SheetTitle>
            コメント <span className="text-sm font-normal text-muted-foreground">{comments.length} 件</span>
          </SheetTitle>
          <Button variant="ghost" size="icon" aria-label="閉じる" onClick={() => onOpenChange(false)}>
            <X />
          </Button>
        </SheetHeader>
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4">
          {comments.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              コメントはありません。本文の文字列を選ぶと追加できます。
            </p>
          ) : (
            <>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  aria-label="すべて選択"
                  checked={all}
                  indeterminate={mixed}
                  onCheckedChange={(checked) => setSelected(null, checked)}
                />
                すべて選択
              </label>
              <ul className="space-y-3">
                {comments.map((comment, index) => (
                  <li key={comment.id} className="space-y-2 rounded-lg border border-border p-3">
                    <div className="flex items-start gap-2">
                      <Checkbox
                        aria-label={`${index + 1} 件目を選択`}
                        checked={comment.selected}
                        onCheckedChange={(checked) => setSelected(comment.id, checked)}
                      />
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left text-xs text-primary hover:underline"
                        onClick={() => onLocate(comment)}
                      >
                        {placeOf(comment)}
                      </button>
                      {editingId !== comment.id && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            aria-label="修正"
                            onClick={() => startEdit(comment)}
                          >
                            <Pencil />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            aria-label="削除"
                            onClick={() => {
                              remove(comment.id);
                              onChanged();
                            }}
                          >
                            <Trash2 />
                          </Button>
                        </>
                      )}
                    </div>
                    <blockquote className="line-clamp-2 border-l-2 border-border pl-2 text-xs text-muted-foreground">
                      「{comment.quote}」
                    </blockquote>
                    {editingId === comment.id ? (
                      <div className="space-y-2">
                        <Textarea
                          aria-label="コメント"
                          autoFocus
                          value={draft}
                          onChange={(event) => setDraft(event.target.value)}
                          onKeyDown={(event) => event.key === "Escape" && setEditingId(null)}
                        />
                        {invalid && <p className="text-xs text-destructive">コメントを入力してください。</p>}
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => setEditingId(null)}>
                            キャンセル
                          </Button>
                          <Button size="sm" onClick={save}>
                            保存
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{comment.body}</p>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        {comments.length > 0 && (
          <div className="flex gap-2 border-t border-border p-4">
            <Button disabled={chosen.length === 0} onClick={onCopy}>
              選択 {chosen.length} 件をコピー
            </Button>
            {github !== null && (
              <Button variant="outline" disabled={chosen.length === 0} onClick={onIssue}>
                Issue を作成
              </Button>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
