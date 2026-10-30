import { Link } from "@tanstack/react-router";

import { firstPagePath } from "@/features/docs/doc-view/nav";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import type { NavTab } from "@/shared/api/generated/model";
import { cn } from "@/shared/lib/utils";

type Props = {
  tabs: NavTab[];
  currentIndex: number;
  source: string;
  search: DocViewSearch;
  onEmptyTab: (tab: NavTab) => void;
};

const TAB_CLASS = "whitespace-nowrap border-b-2 px-3 py-2 text-sm hover:text-foreground";

/** 配信元の文書の種類のタブ。画面の移動なので `nav` のリンクにする */
export const DocTabs = ({ tabs, currentIndex, source, search, onEmptyTab }: Props) => (
  <nav aria-label="文書の種類" className="flex overflow-x-auto border-b border-border">
    {tabs.map((tab, index) => {
      const path = firstPagePath(tab);
      const current = index === currentIndex;
      const className = cn(
        TAB_CLASS,
        current
          ? "border-primary font-medium text-foreground"
          : "border-transparent text-muted-foreground",
      );
      return path === null ? (
        <button
          key={tab.title}
          type="button"
          aria-current={current ? "page" : undefined}
          className={className}
          onClick={() => onEmptyTab(tab)}
        >
          {tab.title}
        </button>
      ) : (
        <Link
          key={tab.title}
          to="/$source/$"
          params={{ source, _splat: path }}
          search={{ rev: search.rev, base: search.base }}
          aria-current={current ? "page" : undefined}
          className={className}
        >
          {tab.title}
        </Link>
      );
    })}
  </nav>
);
