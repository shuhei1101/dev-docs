import { Link } from "@tanstack/react-router";
import { Fragment } from "react";

import { firstPagePath, type ActivePage } from "@/features/docs/doc-view/nav";
import type { DocViewSearch } from "@/features/docs/doc-view/search";
import type { NavTab } from "@/shared/api/generated/model";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbSeparator,
} from "@/shared/components/ui/breadcrumb";

type Props = {
  source: string;
  active: ActivePage;
  emptyTab: NavTab | null;
  search: DocViewSearch;
};

/**
 * `{配信元の ID}` / `{タブ名}` / `{group}` / `{文書の名前}`。配信元とタブだけをリンクにする。
 * 文書の無いタブを選んでいれば `{配信元の ID}` / `{そのタブ名}` だけを並べ、タブ名を末尾の項目にする
 */
export const DocBreadcrumb = ({ source, active, emptyTab, search }: Props) => {
  const tabPath = firstPagePath(active.tab);
  const query = { rev: search.rev, base: search.base };
  const trail: string[] = emptyTab
    ? []
    : [active.group, active.page?.title ?? null].filter(
        (item): item is string => item !== null,
      );
  return (
    <Breadcrumb aria-label="パンくず">
      <BreadcrumbList>
        <BreadcrumbItem>
          <Link
            to="/$source"
            params={{ source }}
            search={query}
            className="hover:text-foreground"
          >
            {source}
          </Link>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          {emptyTab ? (
            <span aria-current="page" className="font-normal text-foreground">
              {emptyTab.title}
            </span>
          ) : tabPath === null ? (
            <span>{active.tab.title}</span>
          ) : (
            <Link
              to="/$source/$"
              params={{ source, _splat: tabPath }}
              search={{ ...query, tab: search.tab }}
              className="hover:text-foreground"
            >
              {active.tab.title}
            </Link>
          )}
        </BreadcrumbItem>
        {trail.map((label, index) => (
          <Fragment key={`${index}:${label}`}>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              {index === trail.length - 1 ? (
                <span
                  aria-current="page"
                  className="font-normal text-foreground"
                >
                  {label}
                </span>
              ) : (
                <span>{label}</span>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
};
