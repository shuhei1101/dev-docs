import { Badge } from "@/shared/components/ui/badge";
import { formatJst } from "@/shared/lib/format";

type Props = {
  title: string;
  kind?: string;
  path?: string;
  updatedAt?: string;
};

/** 文書のタイトルと情報（種類・パス・更新日時） */
export const DocHeader = ({ title, kind, path, updatedAt }: Props) => (
  <header className="space-y-2">
    <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
    {kind !== undefined && (
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Badge variant="secondary">{kind}</Badge>
        {path !== undefined && (
          <code className="font-mono text-xs">{path}</code>
        )}
        {updatedAt !== undefined && (
          <time dateTime={updatedAt}>更新 {formatJst(updatedAt)}</time>
        )}
      </div>
    )}
  </header>
);
