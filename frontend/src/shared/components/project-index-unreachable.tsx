import { CircleAlert } from "lucide-react";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { AppError } from "@/shared/core/app-error";
import { ProjectIndexUnreachableSchema } from "@/shared/core/schema";

export type ProjectIndexUnreachable = { address: string; reason: string };

/** 画面の API の 503 から、接続できなかった project-index のアドレスと理由を取り出す */
export const toProjectIndexUnreachable = (
  error: unknown,
): ProjectIndexUnreachable | null => {
  if (!(error instanceof AppError) || error.status !== 503) return null;
  const parsed = ProjectIndexUnreachableSchema.safeParse(error.problem);
  return parsed.success ? parsed.data.projectIndex : null;
};

type Props = ProjectIndexUnreachable & { onReload: () => void };

/** project-index に接続できなかったことと、接続先・理由・再読み込みを出す */
export const ProjectIndexUnreachableAlert = ({
  address,
  reason,
  onReload,
}: Props) => (
  <Alert variant="destructive">
    <CircleAlert aria-hidden="true" />
    <AlertTitle>project-index に接続できませんでした</AlertTitle>
    <AlertDescription className="space-y-3">
      <p>project-index を起動してから、再読み込みしてください。</p>
      <dl className="space-y-1 text-sm text-foreground">
        <div className="flex gap-4">
          <dt className="w-16 shrink-0 font-medium">接続先</dt>
          <dd className="font-mono text-xs break-all">{address}</dd>
        </div>
        <div className="flex gap-4">
          <dt className="w-16 shrink-0 font-medium">理由</dt>
          <dd className="text-xs break-all">{reason}</dd>
        </div>
      </dl>
      <Button variant="outline" onClick={onReload}>
        再読み込み
      </Button>
    </AlertDescription>
  </Alert>
);
