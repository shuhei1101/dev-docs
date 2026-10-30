import { CircleAlert, CircleCheck, CircleMinus, CircleDashed } from "lucide-react";

import type { SettingsSourceRow } from "@/shared/api/generated/model";
import { Badge } from "@/shared/components/ui/badge";

type Props = { source: SettingsSourceRow };

const LABELS = {
  serving: { text: "配信中", Icon: CircleCheck, variant: "secondary" },
  not_served: { text: "配信していない", Icon: CircleAlert, variant: "destructive" },
  disabled: { text: "無効", Icon: CircleMinus, variant: "outline" },
  pending_reload: { text: "読み直していない", Icon: CircleDashed, variant: "outline" },
} as const;

/** 配信元の状態をアイコンと文言のバッジにし、下に状態の補足を出す */
export const StatusBadge = ({ source }: Props) => {
  const { text, Icon, variant } = LABELS[source.status];
  const notes: string[] = [];
  if (source.status === "not_served") {
    notes.push("起動時の検証で外しました。");
    for (const error of source.errors ?? []) notes.push(`${error.path} ${error.reason}`);
  }
  if (source.status === "disabled") notes.push("enabled が false です");
  if (source.status === "pending_reload") {
    notes.push("ファイルにありますが、まだ読み直していません。");
  }
  if (source.configVersion) {
    notes.push(
      `設定のバージョン ${source.configVersion.config}（サーバーが読めるのは ${source.configVersion.server}）`,
    );
  }
  return (
    <div className="space-y-1">
      <Badge variant={variant}>
        <Icon aria-hidden="true" />
        {text}
      </Badge>
      {notes.map((note) => (
        <p key={note} className="text-xs text-muted-foreground">
          {note}
        </p>
      ))}
    </div>
  );
};
