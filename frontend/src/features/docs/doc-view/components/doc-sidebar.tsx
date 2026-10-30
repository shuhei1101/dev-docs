import { Link } from "@tanstack/react-router";
import { Circle, Minus, Plus } from "lucide-react";

import type { NavItem, NavTab } from "@/shared/api/generated/model";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import { cn } from "@/shared/lib/utils";

type Props = {
  tab: NavTab;
  source: string;
  currentPath: string | null;
  search: DocViewSearch;
  onNavigate?: () => void;
};

const MARKERS = {
  added: { Icon: Plus, label: "追加" },
  modified: { Icon: Circle, label: "変更" },
  deleted: { Icon: Minus, label: "削除" },
} as const;

const Marker = ({ change }: { change: NonNullable<NavItem["change"]> }) => {
  const { Icon, label } = MARKERS[change];
  return (
    <Icon
      aria-label={label}
      role="img"
      className={cn(
        "size-3 shrink-0",
        change === "modified" && "fill-current",
        change === "added" && "text-success",
        change === "modified" && "text-warning",
        change === "deleted" && "text-destructive",
      )}
    />
  );
};

type ItemsProps = Omit<Props, "tab"> & { items: NavItem[] };

const Items = ({
  items,
  source,
  currentPath,
  search,
  onNavigate,
}: ItemsProps) => (
  <ul className="space-y-0.5">
    {items.map((item) =>
      item.kind === "group" ? (
        <li key={`group:${item.title}`}>
          <p className="mt-3 mb-1 px-2 text-xs font-semibold text-muted-foreground">
            {item.title}
          </p>
          <Items
            items={item.items ?? []}
            source={source}
            currentPath={currentPath}
            search={search}
            onNavigate={onNavigate}
          />
        </li>
      ) : (
        <li key={`page:${item.path}`}>
          <Link
            to="/$source/$"
            params={{ source, _splat: item.path ?? "" }}
            search={
              item.change === "deleted"
                ? { rev: search.base }
                : { rev: search.rev, base: search.base }
            }
            aria-current={item.path === currentPath ? "page" : undefined}
            onClick={onNavigate}
            className={cn(
              "flex items-center justify-between gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent",
              item.path === currentPath && "bg-accent font-medium",
            )}
          >
            <span className={cn(item.change === "deleted" && "line-through")}>
              {item.title}
            </span>
            {item.change != null && <Marker change={item.change} />}
          </Link>
        </li>
      ),
    )}
  </ul>
);

/** 選んでいるタブの文書の一覧（サイドバーとドロワーの中身） */
export const DocSidebar = ({ tab, ...rest }: Props) => (
  <nav aria-label="文書の一覧">
    <Items {...rest} items={tab.items} />
  </nav>
);
