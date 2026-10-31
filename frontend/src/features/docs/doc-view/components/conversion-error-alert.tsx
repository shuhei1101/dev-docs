import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import type { ConversionError } from "@/shared/api/generated/model";

type Props = {
  error: ConversionError;
  onRetry: () => void;
};

const EXPLANATIONS: Record<ConversionError["reason"], string> = {
  timeout:
    "配信元の変換のスクリプトが制限時間を超えたため、止めました。スクリプトを修正してから、再読み込みしてください。",
  exit: "配信元の変換のスクリプトが失敗して終わりました。スクリプトを修正してから、再読み込みしてください。",
  not_runnable:
    "配信元の変換のスクリプトを実行できませんでした。スクリプトを修正してから、再読み込みしてください。",
  invalid_yaml:
    "文書の YAML を読めませんでした。ファイルを修正してから、再読み込みしてください。",
};

/** 本文の代わりに出す変換の失敗 */
export const ConversionErrorAlert = ({ error, onRetry }: Props) => {
  const rows =
    error.reason === "invalid_yaml"
      ? [
          ["ファイル", error.file ?? ""],
          ["場所", `${error.line ?? "-"} 行 ${error.column ?? "-"} 列`],
          ["原因", error.detail],
        ]
      : [
          ["種類", error.kind],
          ["スクリプト", error.script ?? ""],
          ["原因", error.detail],
        ];
  return (
    <Alert variant="destructive" role="alert">
      <AlertTitle>本文を変換できませんでした</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{EXPLANATIONS[error.reason]}</p>
        <dl className="space-y-1">
          {rows.map(([label, value]) => (
            <div key={label} className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium">{label}</dt>
              <dd className="font-mono text-xs break-all">{value}</dd>
            </div>
          ))}
        </dl>
        <Button variant="outline" size="sm" onClick={onRetry}>
          再読み込み
        </Button>
      </AlertDescription>
    </Alert>
  );
};
