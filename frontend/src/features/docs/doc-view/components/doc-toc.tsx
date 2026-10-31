import { Circle } from "lucide-react";

import type { TocItem } from "@/features/docs/doc-view/toc";
import { useActiveHeading } from "@/shared/hooks/use-active-heading";
import { cn } from "@/shared/lib/utils";

type Props = {
  items: TocItem[];
  /** `changedSections` の結果（差分を出していないときは渡さない） */
  changed?: Set<string>;
};

/** 本文の右の目次。見出し 2・3 を階層どおりに並べる */
export const DocToc = ({ items, changed }: Props) => {
  const active = useActiveHeading(items.map((item) => item.id));
  return (
    <nav aria-label="目次" className="text-sm">
      <h2 className="mb-2 text-xs font-semibold text-muted-foreground">目次</h2>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id} className={cn(item.level === 3 && "pl-3")}>
            <a
              href={`#${item.id}`}
              aria-current={item.id === active ? "true" : undefined}
              className={cn(
                "flex items-center justify-between gap-2 text-muted-foreground hover:text-foreground",
                item.id === active && "font-medium text-foreground",
              )}
            >
              <span>{item.text}</span>
              {changed?.has(item.text) === true && (
                <Circle
                  aria-hidden="true"
                  className="size-2.5 shrink-0 fill-current text-warning"
                />
              )}
              {changed?.has(item.text) === true && (
                <span className="sr-only">変更</span>
              )}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
};
