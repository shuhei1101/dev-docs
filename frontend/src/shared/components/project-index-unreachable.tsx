import { CircleAlert } from "lucide-react";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { AppError } from "@/shared/core/app-error";
import { ProjectIndexUnreachableSchema } from "@/shared/core/schema";

/** 表示できない理由の種類（接続を断られた・応答が無かった・project-index が処理に失敗した） */
export type ProjectIndexFailureKind = "unreachable" | "timeout" | "failed";

export type ProjectIndexUnreachable = {
  address: string;
  reason: string;
  kind: ProjectIndexFailureKind;
};

const MESSAGES: Record<
  ProjectIndexFailureKind,
  { title: string; description: string }
> = {
  unreachable: {
    title: "project-index に接続できませんでした",
    description: "project-index を起動してから、再読み込みしてください。",
  },
  timeout: {
    title: "project-index から応答がありませんでした",
    description:
      "project-index が配信元を初めて読み込む間は、時間がかかることがあります。しばらく待ってから、再読み込みしてください。",
  },
  failed: {
    title: "project-index が要求を処理できませんでした",
    description:
      "時間をおいて再読み込みすると、開けることがあります。続くときは、project-index のログで原因を確認してください。",
  },
};

/** 画面の API の 503・502 から、project-index のアドレス・理由・理由の種類を取り出す */
export const toProjectIndexUnreachable = (
  error: unknown,
): ProjectIndexUnreachable | null => {
  if (!(error instanceof AppError)) return null;
  if (error.status !== 503 && error.status !== 502) return null;
  const parsed = ProjectIndexUnreachableSchema.safeParse(error.problem);
  return parsed.success ? parsed.data.projectIndex : null;
};

type Props = Omit<ProjectIndexUnreachable, "kind"> & {
  /** 表示できない理由の種類。省くと接続できなかったときの文言 */
  kind?: ProjectIndexFailureKind;
  onReload: () => void;
  /** 見出しの要素の id。接続できない間に押せない操作の `aria-describedby` から指す */
  titleId?: string;
};

/** project-index から文書を受け取れなかったことと、接続先・理由・再読み込みを出す */
export const ProjectIndexUnreachableAlert = ({
  kind = "unreachable",
  address,
  reason,
  onReload,
  titleId,
}: Props) => (
  <Alert variant="destructive">
    <CircleAlert aria-hidden="true" />
    <AlertTitle id={titleId}>{MESSAGES[kind].title}</AlertTitle>
    <AlertDescription className="space-y-3">
      <p className="text-pretty text-foreground">
        {MESSAGES[kind].description}
      </p>
      <dl className="space-y-1 text-sm text-foreground">
        <div className="flex gap-4">
          <dt className="w-16 shrink-0 font-medium">接続先</dt>
          <dd className="min-w-0 font-mono text-xs break-all">{address}</dd>
        </div>
        <div className="flex gap-4">
          <dt className="w-16 shrink-0 font-medium">理由</dt>
          <dd className="min-w-0 text-xs wrap-anywhere">{reason}</dd>
        </div>
      </dl>
      <Button variant="outline" className="text-foreground" onClick={onReload}>
        再読み込み
      </Button>
    </AlertDescription>
  </Alert>
);
