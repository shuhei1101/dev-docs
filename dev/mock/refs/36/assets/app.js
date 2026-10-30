// PR #36 の画面モックの動き
// モックの状態は URL の # に持ち、モック専用の操作列のリンクで切り替える

const root = document.documentElement;

/** data-when・data-open-when に出てくる状態の名前を集める */
function knownStates() {
  const names = new Set(["normal"]);
  for (const el of document.querySelectorAll("[data-when], [data-open-when], [data-current-when]")) {
    const value = el.dataset.when ?? el.dataset.openWhen ?? el.dataset.currentWhen;
    for (const name of value.split(" ")) names.add(name);
  }
  return names;
}

const STATES = knownStates();

/** 今の # が指す状態の名前を返す（状態でない # は通常として扱う） */
function currentState() {
  const name = location.hash.slice(1);
  return STATES.has(name) ? name : "normal";
}

/** 状態に合わせて、出す要素・選択中・開いている重なりを切り替える */
function applyState() {
  const state = currentState();
  root.dataset.state = state;

  for (const el of document.querySelectorAll("[data-when]")) {
    el.hidden = !el.dataset.when.split(" ").includes(state);
  }

  for (const el of document.querySelectorAll("[data-current-when]")) {
    if (el.dataset.currentWhen.split(" ").includes(state)) {
      el.setAttribute("aria-current", "page");
    } else {
      el.removeAttribute("aria-current");
    }
  }

  for (const tab of document.querySelectorAll(".mockbar__tab[href^='#']")) {
    const name = tab.getAttribute("href").slice(1) || "normal";
    if (name === state) {
      tab.setAttribute("aria-current", "page");
    } else {
      tab.removeAttribute("aria-current");
    }
  }

  // ダイアログとポップオーバーは、状態に当たるものだけを開く
  for (const el of document.querySelectorAll("[data-open-when]")) {
    const open = el.dataset.openWhen.split(" ").includes(state);
    if (el instanceof HTMLDialogElement) {
      if (open && !el.open) {
        el.showModal();
        // 保存の失敗のまとめがあれば、そこへフォーカスを移す
        el.querySelector(".error-summary:not([hidden])")?.focus();
      }
      if (!open && el.open) el.close();
    } else if (el.hasAttribute("popover")) {
      if (open && !el.matches(":popover-open")) el.showPopover();
      if (!open && el.matches(":popover-open")) el.hidePopover();
    }
  }
}

/** 重なりを閉じたら、状態を通常に戻す */
function resetStateOnClose(el) {
  const back = () => {
    if (el.dataset.openWhen.split(" ").includes(currentState())) {
      history.replaceState(null, "", location.pathname + location.search);
      applyState();
    }
  };
  if (el instanceof HTMLDialogElement) {
    el.addEventListener("close", back);
  } else {
    el.addEventListener("toggle", (event) => {
      if (event.newState === "closed") back();
    });
  }
}

for (const el of document.querySelectorAll("[data-open-when]")) resetStateOnClose(el);

// ===== 表の列の表示（外した列のセルを隠す） =====

const columnToggles = [...document.querySelectorAll("[data-column-toggle]")];

/** 列の表示の切り替えを表へ当てる */
function applyColumns() {
  const hiddenCount = new Map();
  for (const toggle of columnToggles) {
    const table = document.getElementById(toggle.dataset.columnToggle);
    const cells = table.querySelectorAll(`tr > :nth-child(${toggle.dataset.column})`);
    for (const cell of cells) cell.hidden = !toggle.checked;
    if (!toggle.checked) {
      hiddenCount.set(table.id, (hiddenCount.get(table.id) ?? 0) + 1);
    }
  }
  for (const note of document.querySelectorAll("[data-column-note]")) {
    const count = hiddenCount.get(note.dataset.columnNote) ?? 0;
    note.hidden = count === 0;
    note.textContent = `${count} 列を隠しています`;
  }
}

/** 状態に合わせて、列の表示の初期値を決める */
function resetColumns() {
  for (const toggle of columnToggles) {
    toggle.checked = toggle.dataset.uncheckedWhen !== currentState();
  }
  applyColumns();
}

for (const toggle of columnToggles) toggle.addEventListener("change", applyColumns);

addEventListener("hashchange", () => {
  applyState();
  resetColumns();
});
applyState();
resetColumns();

// ===== 明暗の切り替え（押すたびにシステムの設定の反対へ固定し、もう一度押すと戻す） =====

const SCHEME_KEY = "dev-docs-color-scheme";
const meta = document.querySelector('meta[name="color-scheme"]');
const systemDark = matchMedia("(prefers-color-scheme: dark)");

for (const toggle of document.querySelectorAll("[data-scheme-toggle]")) {
  toggle.setAttribute("aria-pressed", String(Boolean(localStorage.getItem(SCHEME_KEY))));
  toggle.addEventListener("click", () => {
    const pinned = localStorage.getItem(SCHEME_KEY);
    if (pinned) {
      localStorage.removeItem(SCHEME_KEY);
      meta.content = "light dark";
      delete root.dataset.scheme;
    } else {
      const scheme = systemDark.matches ? "light" : "dark";
      localStorage.setItem(SCHEME_KEY, scheme);
      meta.content = scheme;
      root.dataset.scheme = scheme;
    }
    for (const other of document.querySelectorAll("[data-scheme-toggle]")) {
      other.setAttribute("aria-pressed", String(!pinned));
    }
  });
}

// ===== 検索のショートカット（Ctrl+K・/） =====

const searchDialog = document.getElementById("search-dialog");

/** 入力欄にフォーカスがあるか */
function isTyping(target) {
  return target instanceof HTMLElement && target.closest("input, textarea, select, [contenteditable]");
}

if (searchDialog) {
  addEventListener("keydown", (event) => {
    // IME で変換中のキーは無視する
    if (event.isComposing || event.keyCode === 229) return;
    const mod = event.ctrlKey || event.metaKey;
    const slash = event.key === "/" && !mod && !isTyping(event.target);
    if ((mod && event.key.toLowerCase() === "k") || slash) {
      event.preventDefault();
      if (!searchDialog.open) searchDialog.showModal();
    }
  });
}

// ===== コメントのパネル（モーダルでないので Esc を自分で受ける） =====

const commentPanel = document.getElementById("comment-panel");

if (commentPanel) {
  commentPanel.addEventListener("toggle", (event) => {
    if (event.newState === "open") commentPanel.querySelector("h2")?.focus();
  });
  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !event.isComposing && commentPanel.matches(":popover-open")) {
      commentPanel.hidePopover();
    }
  });
}

// コメントを選ぶと、本文のその箇所まで動かして示す
for (const jump of document.querySelectorAll("[data-jump]")) {
  jump.addEventListener("click", () => {
    const target = document.getElementById(jump.dataset.jump);
    target.scrollIntoView({ block: "center" });
    target.classList.add("is-flash");
    setTimeout(() => target.classList.remove("is-flash"), 1200);
  });
}

// ===== 保存の失敗のまとめから入力欄へ移る =====

for (const link of document.querySelectorAll(".error-summary a")) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    document.getElementById(link.getAttribute("href").slice(1)).focus();
  });
}

// 入力のあるダイアログは、Esc で閉じる前に確かめる
for (const dialog of document.querySelectorAll("dialog[data-confirm-close]")) {
  dialog.addEventListener("cancel", (event) => {
    if (!confirm(dialog.dataset.confirmClose)) event.preventDefault();
  });
}
