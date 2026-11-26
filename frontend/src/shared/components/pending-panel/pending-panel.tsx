import { Undo2 } from "lucide-react";
import { useState } from "react";

import { useCommitEdits, useRestartFromLatest } from "@/shared/components/pending-panel/queries";
import {
  type EditValue,
  type PendingEdit,
  usePendingEdits,
  usePendingEditsStore,
} from "@/shared/stores/pending-edits-store";
import type { CommitResult, ConflictResult, ConflictScript } from "@/shared/api/generated/model";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Label } from "@/shared/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";
import { Textarea } from "@/shared/components/ui/textarea";
import { AppError, type Problem } from "@/shared/core/app-error";
import { useMediaQuery } from "@/shared/hooks/use-media-query";

const OP_LABEL = { update: "変更", add: "追加", delete: "削除" } as const;
const MESSAGE_MAX = 200;
const SHA_CHARS = 7;
const NARROW_QUERY = "(max-width: 47.99rem)";
/** 編集を始めたときのコミットが起点に使用できないときの problem の `title` */
const BASE_COMMIT_UNUSABLE = "BaseCommitUnusableError";

type Outcome =
  | { kind: "diff"; result: CommitResult }
  | { kind: "committed"; result: CommitResult }
  | { kind: "conflict"; conflict: ConflictResult; labels: string[] }
  | { kind: "failed"; problem: Problem | null; message: string }
  | { kind: "dropped"; labels: string[] }
  | null;

const toText = (value: EditValue | undefined): string =>
  Array.isArray(value) ? value.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).join(", ") : (value ?? "");

/** 本文の変更の、パネルに 1 行で出せない値（ファイル全体・表・複数行）の案内 */
const DIFF_ONLY = "差分確認で表示します";

/** 本文の変更で、変更前と変更後を 1 行で並べられない値か */
const isDiffOnly = (edit: PendingEdit, path: string, value: EditValue): boolean =>
  edit.kind === "body" &&
  (path === "@file" || typeof value !== "string" || value.includes("\n") || toText(edit.before[path]).includes("\n"));

/** 失敗の Problem Details の `errors[]` を、変更の `key` ごとの理由にする */
const reasonsOf = (problem: Problem | null): Map<string, string[]> => {
  const reasons = new Map<string, string[]>();
  for (const item of problem?.errors ?? []) {
    if (item.key === undefined || item.key === null) continue;
    const text = item.path ? `${item.path}: ${item.reason}` : item.reason;
    reasons.set(item.key, [...(reasons.get(item.key) ?? []), text]);
  }
  return reasons;
};

/** 差分の行を、行頭の `-`・`+` で色分けする */
const Diff = ({ text }: { text: string }) => (
  <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
    {text.split("\n").map((line, index) => (
      <span
        key={`${index}:${line}`}
        className={
          line.startsWith("+")
            ? "block text-green-700 dark:text-green-400"
            : line.startsWith("-")
              ? "block text-red-700 dark:text-red-400"
              : "block"
        }
      >
        {line}
      </span>
    ))}
  </pre>
);

type EditItemProps = {
  edit: PendingEdit;
  diff: string | undefined;
  reasons: string[];
  busy: boolean;
  onLocate: () => void;
  onDiscard: () => void;
};

/** 編集中の変更 1 件と、その差分・理由 */
const EditItem = ({ edit, diff, reasons, busy, onLocate, onDiscard }: EditItemProps) => (
  <li className="rounded-md border p-2">
    <div className="flex items-start gap-2">
      <Badge variant="outline">{OP_LABEL[edit.op]}</Badge>
      <button
        type="button"
        className="flex-1 text-left text-sm underline-offset-2 hover:underline"
        aria-label={`${edit.label} の行へ移動`}
        onClick={onLocate}
      >
        {edit.label}
        {edit.op === "update" &&
          Object.entries(edit.values).map(([column, value]) =>
            isDiffOnly(edit, column, value) ? (
              <span key={column} className="mt-1 block text-xs text-muted-foreground">
                {DIFF_ONLY}
              </span>
            ) : (
              <span key={column} className="mt-1 block font-mono text-xs">
                {toText(edit.before[column])} → {toText(value)}
              </span>
            ),
          )}
      </button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`${edit.label} を元に戻す`}
        disabled={busy}
        onClick={onDiscard}
      >
        <Undo2 />
      </Button>
    </div>
    {diff !== undefined && <Diff text={diff} />}
    {reasons.map((reason) => (
      <p key={reason} className="mt-1 text-xs text-destructive">
        {reason}
      </p>
    ))}
  </li>
);

type ConfirmProps = {
  open: boolean;
  source: string;
  branch: string;
  count: number;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onCommit: (message: string) => void;
};

/** 既定のブランチへプッシュする前の確認 */
const CommitConfirm = ({ open, source, branch, count, busy, onOpenChange, onCommit }: ConfirmProps) => {
  const [message, setMessage] = useState("");
  const tooLong = message.length > MESSAGE_MAX;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>コミットしますか？</DialogTitle>
          <DialogDescription>
            {source} の {branch} へ、{count} 件の変更を 1 つのコミットにしてプッシュします。プッシュした後は取り消せません。
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="commit-message">コミットの説明</Label>
          <Textarea
            id="commit-message"
            value={message}
            aria-invalid={tooLong}
            aria-describedby={tooLong ? "commit-message-error" : undefined}
            onChange={(event) => setMessage(event.target.value)}
          />
          {tooLong && (
            <p id="commit-message-error" className="text-xs text-destructive">
              200 文字以内で入力してください
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            キャンセル
          </Button>
          <Button disabled={busy || tooLong || message.trim() === ""} onClick={() => onCommit(message)}>
            コミット
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/** 送信の失敗のまとめ */
const FailureSummary = ({ outcome }: { outcome: Extract<Outcome, { kind: "failed" }> }) => {
  const hasReasons = (outcome.problem?.errors ?? []).some((item) => item.key);
  const unusable = outcome.problem?.title === BASE_COMMIT_UNUSABLE;
  return (
    <Alert variant="destructive" role="alert">
      <AlertTitle>{outcome.problem?.title ?? "コミットできませんでした"}</AlertTitle>
      <AlertDescription>
        <p>
          {hasReasons
            ? "コミットできませんでした。変更ごとの理由を確認してください。"
            : (outcome.problem?.detail ?? outcome.message)}
        </p>
        {(outcome.problem?.nextSteps ?? []).map((step) => (
          <p key={step}>{step}</p>
        ))}
        <p>
          {unusable
            ? "編集中の変更はそのままです。「最新の内容で続ける」を押すと、最新の内容を再取得し、変更を残したまま送信できます。"
            : "編集中の変更はそのままです。"}
        </p>
      </AlertDescription>
    </Alert>
  );
};

/** 衝突したときのスクリプトの結果の文 */
const ScriptResult = ({ script }: { script: ConflictScript | null }) => {
  if (script === null) {
    return <p>衝突したときのスクリプトが登録されていないため、PR は作成していません。ブランチはこの端末のクローンにだけあります。</p>;
  }
  if (script.exitCode === 0 && !script.timedOut) {
    return script.prUrl ? (
      <p>
        <a className="underline underline-offset-2" href={script.prUrl} target="_blank" rel="noreferrer">
          PR を開く
        </a>
      </p>
    ) : (
      <p>衝突したときのスクリプトを実行しました。</p>
    );
  }
  return (
    <div>
      <p className="text-destructive">
        {script.timedOut
          ? "衝突したときのスクリプトが制限時間を過ぎたため止めました。"
          : `衝突したときのスクリプトが失敗しました（終了コード ${script.exitCode}）。`}
      </p>
      {script.stderr !== "" && (
        <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 font-mono text-xs whitespace-pre-wrap text-foreground">
          {script.stderr}
        </pre>
      )}
    </div>
  );
};

/** 衝突して修正をブランチに残した結果のまとめ */
const ConflictSummary = ({ outcome }: { outcome: Extract<Outcome, { kind: "conflict" }> }) => (
  <Alert role="status">
    <AlertTitle>ほかの変更と衝突したため、修正をブランチに残しました</AlertTitle>
    <AlertDescription>
      <p>
        ブランチ <code className="font-mono">{outcome.conflict.branch}</code>（編集を始めたときの{" "}
        <code className="font-mono">{outcome.conflict.baseCommit.slice(0, SHA_CHARS)}</code> から）
      </p>
      <ScriptResult script={outcome.conflict.script} />
      <p className="mt-2 font-medium">ブランチに残した変更</p>
      <ul className="list-disc pl-4">
        {outcome.labels.map((label) => (
          <li key={label}>{label}</li>
        ))}
      </ul>
      <p className="mt-2 font-medium">衝突した理由</p>
      <ul className="list-disc pl-4">
        {outcome.conflict.reasons.map((item) => (
          <li key={`${item.key ?? ""}:${item.reason}`}>{item.reason}</li>
        ))}
      </ul>
      <p className="mt-2">ブランチに残した変更は、編集中の変更から除きました。</p>
    </AlertDescription>
  </Alert>
);

/** 差分確認が衝突を返却したときの、変更の `key` ごとの理由 */
const conflictReasonsOf = (conflict: ConflictResult | null | undefined): Map<string, string[]> => {
  const reasons = new Map<string, string[]>();
  for (const item of conflict?.reasons ?? []) {
    if (item.key === null) continue;
    reasons.set(item.key, [...(reasons.get(item.key) ?? []), item.reason]);
  }
  return reasons;
};

/** 直前の結果を、変更の `key` ごとの差分と理由にする */
const outcomeByEdit = (outcome: Outcome) => ({
  diffs: new Map(
    outcome?.kind === "diff" ? outcome.result.results.map((item) => [item.key, item.diff]) : [],
  ),
  reasons:
    outcome?.kind === "diff"
      ? conflictReasonsOf(outcome.result.conflict)
      : reasonsOf(outcome?.kind === "failed" ? outcome.problem : null),
});

/** 差分確認で衝突する（このままコミットすると修正がブランチに残る）ことの注意 */
const DryRunConflictNotice = () => (
  <Alert variant="destructive" role="alert">
    <AlertTitle>コミットすると、ほかの変更と衝突して修正がブランチに残ります</AlertTitle>
  </Alert>
);

/** 「最新の内容で続ける」で、最新の値と食い違うため取り消した変更 */
const DroppedSummary = ({ labels }: { labels: string[] }) => (
  <Alert role="status">
    <AlertTitle>最新の内容と食い違うため、次の変更を取り消しました</AlertTitle>
    <AlertDescription>
      <ul className="list-disc pl-4">
        {labels.map((label) => (
          <li key={label}>{label}</li>
        ))}
      </ul>
      <p className="mt-2">最新の値を確認して、もう一度編集してください。</p>
    </AlertDescription>
  </Alert>
);

/** コミットの結果か送信の失敗のまとめ */
const OutcomeSummary = ({ outcome }: { outcome: Outcome }) => {
  if (outcome?.kind === "failed") return <FailureSummary outcome={outcome} />;
  if (outcome?.kind === "conflict") return <ConflictSummary outcome={outcome} />;
  if (outcome?.kind === "dropped") return <DroppedSummary labels={outcome.labels} />;
  if (outcome?.kind === "diff" && outcome.result.conflict) return <DryRunConflictNotice />;
  if (outcome?.kind !== "committed" || !outcome.result.commit) return null;
  return (
    <Alert role="status">
      <AlertTitle>
        {outcome.result.commit.branch} にコミットしました（{outcome.result.commit.sha.slice(0, SHA_CHARS)}）
      </AlertTitle>
    </Alert>
  );
};

type Props = {
  source: string;
  branch: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onLocate: (edit: PendingEdit) => void;
};

/** 配信元の編集中の変更と、差分確認・コミットの結果と失敗 */
export const PendingPanel = ({ source, branch, open, onOpenChange, onLocate }: Props) => {
  const edits = usePendingEdits(source);
  const remove = usePendingEditsStore((state) => state.remove);
  const commit = useCommitEdits(source);
  const restart = useRestartFromLatest(source);
  const narrow = useMediaQuery(NARROW_QUERY);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const branchLabel = branch ?? "既定のブランチ";

  const send = async (dryRun: boolean, message?: string) => {
    setConfirmOpen(false);
    const labels = edits.map((edit) => edit.label);
    try {
      const result = await commit.mutateAsync({ dryRun, message });
      if (!dryRun && result.conflict) {
        setOutcome({ kind: "conflict", conflict: result.conflict, labels });
        return;
      }
      setOutcome({ kind: dryRun ? "diff" : "committed", result });
    } catch (error) {
      setOutcome({
        kind: "failed",
        problem: error instanceof AppError ? error.problem : null,
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  /** 編集中の変更を残したまま、メタデータを最新の内容で再取得し、最新の値と食い違う変更を取り消す */
  const restartFromLatest = async () => {
    try {
      const { dropped } = await restart.mutateAsync();
      setOutcome(dropped.length > 0 ? { kind: "dropped", labels: dropped.map((edit) => edit.label) } : null);
    } catch (error) {
      setOutcome({
        kind: "failed",
        problem: error instanceof AppError ? error.problem : null,
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const { diffs, reasons } = outcomeByEdit(outcome);
  const unusable = outcome?.kind === "failed" && outcome.problem?.title === BASE_COMMIT_UNUSABLE;
  const busy = commit.isPending || restart.isPending;

  return (
    <>
      <Sheet modal={false} disablePointerDismissal open={open} onOpenChange={onOpenChange}>
        <SheetContent
          side={narrow ? "bottom" : "right"}
          overlay={false}
          className={
            narrow ? "max-h-2/3 w-full overflow-y-auto" : "top-12! bottom-0! h-auto! w-96 max-w-full overflow-y-auto"
          }
        >
          <SheetHeader>
            <SheetTitle>編集中</SheetTitle>
            {edits.length > 0 && (
              <SheetDescription>
                {source} の {branchLabel} へ、{edits.length} 件の変更をまとめてコミットします。
              </SheetDescription>
            )}
          </SheetHeader>
          <div className="flex flex-col gap-3 px-4">
            <OutcomeSummary outcome={outcome} />
            {edits.length === 0 && <p className="text-sm text-muted-foreground">編集中の変更はありません。</p>}
            <ul className="flex flex-col gap-2">
              {edits.map((edit) => (
                <EditItem
                  key={edit.key}
                  edit={edit}
                  diff={diffs.get(edit.key)}
                  reasons={reasons.get(edit.key) ?? []}
                  busy={busy}
                  onLocate={() => onLocate(edit)}
                  onDiscard={() => remove(source, edit.key)}
                />
              ))}
            </ul>
            {edits.length > 0 && (
              <div className="flex gap-2 pb-4">
                <Button variant="outline" disabled={busy} onClick={() => void send(true)}>
                  差分確認
                </Button>
                {unusable ? (
                  <Button disabled={busy} onClick={() => void restartFromLatest()}>
                    最新の内容で続ける
                  </Button>
                ) : (
                  <Button disabled={busy} onClick={() => setConfirmOpen(true)}>
                    {outcome?.kind === "failed" ? "再試行" : "コミット"}
                  </Button>
                )}
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
      <CommitConfirm
        open={confirmOpen}
        source={source}
        branch={branchLabel}
        count={edits.length}
        busy={busy}
        onOpenChange={setConfirmOpen}
        onCommit={(message) => void send(false, message)}
      />
    </>
  );
};
