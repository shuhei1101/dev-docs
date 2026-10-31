import { Link } from "@tanstack/react-router";
import {
  createColumnHelper,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { Pencil, Trash2 } from "lucide-react";

import { StatusBadge } from "@/features/settings/settings/components/status-badge";
import type { SettingsSourceRow } from "@/shared/api/generated/model";
import { Button } from "@/shared/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

type Props = {
  sources: SettingsSourceRow[];
  onEdit: (index: number) => void;
  onRemove: (index: number) => void;
};

const features = tableFeatures({});
const helper = createColumnHelper<typeof features, SettingsSourceRow>();

/** 配信元の一覧の表。並べ替え・絞り込みはしない */
export const SourceTable = ({ sources, onEdit, onRemove }: Props) => {
  const columns = helper.columns([
    helper.display({
      id: "id",
      header: "配信元",
      cell: ({ row }) =>
        row.original.status === "serving" && row.original.id ? (
          <Link
            to="/$source"
            params={{ source: row.original.id }}
            className="font-mono text-primary hover:underline"
          >
            {row.original.id}
          </Link>
        ) : (
          <span className="font-mono">{row.original.id}</span>
        ),
    }),
    helper.display({
      id: "config",
      header: "設定ファイル",
      cell: ({ row }) => (
        <div className="space-y-0.5">
          {row.original.config.map((file) => (
            <p key={file} className="font-mono text-xs break-all">
              {file}
            </p>
          ))}
        </div>
      ),
    }),
    helper.display({
      id: "status",
      header: "状態",
      cell: ({ row }) => <StatusBadge source={row.original} />,
    }),
    helper.display({
      id: "actions",
      header: "操作",
      cell: ({ row }) => {
        const name = row.original.id ?? `${row.index + 1} 行目`;
        return (
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`${name} を編集`}
              onClick={() => onEdit(row.index)}
            >
              <Pencil />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`${name} を削除`}
              onClick={() => onRemove(row.index)}
            >
              <Trash2 />
            </Button>
          </div>
        );
      },
    }),
  ]);
  const table = useTable({ features, columns, data: sources });

  return (
    <div className="overflow-x-auto">
      <Table aria-label="配信元の表">
        <TableHeader>
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id}>
              {group.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder ? null : (
                    <table.FlexRender header={header} />
                  )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getAllCells().map((cell) => (
                <TableCell key={cell.id} className="align-top">
                  <table.FlexRender cell={cell} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
