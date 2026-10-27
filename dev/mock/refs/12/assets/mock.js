// PR #12 の画面モックで共有する振る舞い

// Invoker Commands を持たないブラウザだけ polyfill を読む
if (!("commandForElement" in HTMLButtonElement.prototype)) {
  import("https://esm.run/invokers-polyfill");
}

// モック専用: ?state= で見せる状態を選ぶ（無ければ最初の状態のリンク）
const stateLinks = [...document.querySelectorAll(".mockbar__tab[data-state]")];
const state = new URLSearchParams(location.search).get("state") ?? stateLinks[0]?.dataset.state;
for (const link of stateLinks) {
  if (link.dataset.state === state) {
    link.classList.add("is-current");
    link.setAttribute("aria-current", "page");
  }
}
// data-states に今の状態を含まない要素は出さない
for (const element of document.querySelectorAll("[data-states]")) {
  element.hidden = !element.dataset.states.split(" ").includes(state);
}

// モック専用: 開いている案のタブを強調する
const variant = location.pathname.split("/").filter(Boolean).at(-2);
for (const tab of document.querySelectorAll(".mockbar__tab[data-variant]")) {
  if (tab.dataset.variant === variant) {
    tab.classList.add("is-current");
    tab.setAttribute("aria-current", "page");
  }
}

// 選んだタブが帯の外にあるときは、帯を横にスクロールして見せる
const tabBar = document.querySelector(".tabs");
const currentTab = tabBar?.querySelector(".tabs__item.is-current:not([hidden])");
if (currentTab && currentTab.offsetLeft + currentTab.offsetWidth > tabBar.clientWidth) {
  tabBar.scrollLeft = currentTab.offsetLeft - tabBar.clientWidth / 2 + currentTab.offsetWidth / 2;
}

// 明暗の切り替え（システムの設定 ⇄ その反対の 2 状態）
const meta = document.querySelector('meta[name="color-scheme"]');
const toggle = document.getElementById("scheme-toggle");
const systemDark = matchMedia("(prefers-color-scheme: dark)");
const sync = () => toggle?.setAttribute("aria-pressed", String(meta.content !== "light dark"));
toggle?.addEventListener("click", () => {
  if (meta.content === "light dark") {
    const opposite = systemDark.matches ? "light" : "dark";
    meta.content = opposite;
    document.documentElement.dataset.scheme = opposite;
    localStorage.setItem("dev-docs-color-scheme", opposite);
  } else {
    meta.content = "light dark";
    delete document.documentElement.dataset.scheme;
    localStorage.removeItem("dev-docs-color-scheme");
  }
  sync();
});
sync();

// / キーで検索を開く（検索を持つ画面だけ）
const search = document.getElementById("search");
if (search) {
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !event.target.closest("input, textarea")) {
      event.preventDefault();
      search.showPopover();
      document.getElementById("search-input").focus();
    }
  });
}

// 列見出しの押下で 昇順 → 降順 → 解除 を巡る
for (const table of document.querySelectorAll("table[data-sortable]")) {
  const body = table.tBodies[0];
  const initial = [...body.rows];
  const headers = [...table.tHead.rows[0].cells];
  for (const [index, header] of headers.entries()) {
    const button = header.querySelector(".sort-button");
    if (!button) continue;
    button.addEventListener("click", () => {
      const next = { none: "ascending", ascending: "descending", descending: "none" }[header.getAttribute("aria-sort") ?? "none"];
      for (const other of headers) other.removeAttribute("aria-sort");
      if (next === "none") {
        body.append(...initial);
        return;
      }
      header.setAttribute("aria-sort", next);
      const key = (row) => row.cells[index].dataset.sortValue ?? row.cells[index].textContent.trim();
      const sorted = [...initial].sort((a, b) => key(a).localeCompare(key(b), "ja"));
      if (next === "descending") sorted.reverse();
      body.append(...sorted);
    });
  }
}

// 列の表示の切り替え（メニューのチェックと列の data-column を対応させる）
for (const menu of document.querySelectorAll("[data-columns-for]")) {
  const table = document.getElementById(menu.dataset.columnsFor);
  const checks = [...menu.querySelectorAll("input[data-column]")];
  const apply = () => {
    for (const check of checks) {
      for (const cell of table.querySelectorAll(`[data-column="${check.dataset.column}"]`)) {
        cell.hidden = !check.checked;
      }
    }
  };
  for (const check of checks) check.addEventListener("change", apply);
  menu.querySelector(".menu__reset").addEventListener("click", () => {
    for (const check of checks) check.checked = true;
    apply();
  });
  apply();
}
