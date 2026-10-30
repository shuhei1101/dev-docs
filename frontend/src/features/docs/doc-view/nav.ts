import type { NavItem, NavTab } from "@/shared/api/generated/model";

export type ActivePage = {
  tab: NavTab;
  group: string | null;
  page: NavItem | null;
};

const findPage = (
  items: NavItem[],
  path: string,
  group: string | null,
): { group: string | null; page: NavItem } | null => {
  for (const item of items) {
    if (item.kind === "page") {
      if (item.path === path) return { group, page: item };
    } else {
      const found = findPage(item.items ?? [], path, item.title);
      if (found) return found;
    }
  }
  return null;
};

/** `active` のタブから `path` の page とその group を探す */
export const findActivePage = (tabs: NavTab[], path: string): ActivePage => {
  const tab = tabs.find((item) => item.active) ?? tabs[0];
  const found = findPage(tab.items, path, null);
  return { tab, group: found?.group ?? null, page: found?.page ?? null };
};

/** タブのサイドバーの一番上の page のパスを返す */
export const firstPagePath = (tab: NavTab): string | null => {
  const walk = (items: NavItem[]): string | null => {
    for (const item of items) {
      if (item.kind === "page") return item.path ?? null;
      const found = walk(item.items ?? []);
      if (found !== null) return found;
    }
    return null;
  };
  return walk(tab.items);
};

/** ブラウザのタブに出すタイトルを作る */
export const pageTitle = (active: ActivePage, source: string): string =>
  `${active.page?.title ?? active.tab.title} | ${source} | dev-docs`;
