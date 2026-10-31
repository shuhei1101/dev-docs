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

/** `tabIndex` のタブ（省いたか、`path` がそのタブに無いときは `active` のタブ）から `path` の page とその group を探す */
export const findActivePage = (
  tabs: NavTab[],
  path: string,
  tabIndex?: number,
): ActivePage => {
  const selected = tabIndex === undefined ? undefined : tabs[tabIndex];
  const inSelected = selected && findPage(selected.items, path, null);
  // 選んだタブに文書があればそのタブ、無ければ active のタブを現在地にする
  if (selected && inSelected) {
    return { tab: selected, group: inSelected.group, page: inSelected.page };
  }
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
export const pageTitle = (
  active: ActivePage,
  source: string,
  emptyTab: NavTab | null = null,
): string =>
  `${emptyTab?.title ?? active.page?.title ?? active.tab.title} | ${source} | dev-docs`;
