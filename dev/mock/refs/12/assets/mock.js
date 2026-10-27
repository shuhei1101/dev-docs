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

// 選んだタブが帯の外にあるときは、帯を横にスクロールして見せる
const tabBar = document.querySelector(".tabs:not([hidden])");
const currentTab = tabBar?.querySelector(".tabs__item.is-current");
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

// モック専用: data-open-states に今の状態を含むダイアログを開いて見せる
for (const dialog of document.querySelectorAll("dialog[data-open-states]")) {
  if (dialog.dataset.openStates.split(" ").includes(state)) dialog.showModal();
}

// ===== 本文の描画 =====

// 本文の Markdown を mdmark で描く（差分の元があれば差分を強調する）
const articles = [...document.querySelectorAll("article.markdown-body")];
if (articles.length) {
  const mdmark = await import("https://cdn.jsdelivr.net/gh/shuhei1101/mdmark@v0.8.0/dist/index.js");
  for (const article of articles) {
    const markdown = article.querySelector("textarea[data-mdmark-source]").value;
    const previous = article.querySelector("textarea[data-mdmark-diff-source]")?.value;
    // 差分の元は ?diff= で指したリビジョンと今の 2 つ
    const contents = { current: markdown, previous };
    const diffSource = previous && {
      revisions: async () => [
        { id: "current", at: "2026-10-26T12:00:00+09:00", label: "3f9c2ab" },
        { id: "previous", at: "2026-10-20T12:00:00+09:00", label: "8d41e07" },
      ],
      content: async ({ revisionId }) => contents[revisionId],
    };
    mdmark.mount(article, diffSource ? { markdown, diffSource, docId: article.dataset.docPath } : { markdown });
  }
}

// 出ている本文の見出しから目次を作る
const visibleArticle = articles.find((article) => !article.hidden);
for (const list of document.querySelectorAll("[data-toc-list]")) {
  const headings = visibleArticle ? [...visibleArticle.querySelectorAll("h2[id]")] : [];
  // 右の目次は最初の見出しを今いる場所として強調する
  const marksCurrent = Boolean(list.closest(".toc"));
  list.innerHTML = headings.map((h, i) => `<li><a href="#${encodeURIComponent(h.id)}"${marksCurrent && i === 0 ? ' class="is-current" aria-current="location"' : ""}>${h.textContent.trim()}</a></li>`).join("");
}

// 表の上の件数と列の表示を、見出しの直後の表の前へ移し、列の表示の切り替えを付ける
for (const tools of document.querySelectorAll(".table-tools[data-tools-for]")) {
  const article = articles.find((a) => a.dataset.states === tools.dataset.states);
  const heading = [...article.querySelectorAll("h2")].find((h) => h.textContent.includes(tools.dataset.toolsFor));
  const table = [...article.querySelectorAll("table")].find((t) => heading.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING);
  (table.closest(".mdmark-table") ?? table).before(tools);
  // 見出しの行と同じ数のセルを持つ行だけを対象にする（行の詳細の行は除く）
  const columnCount = table.tHead.rows[0].cells.length;
  const rows = [...table.rows].filter((row) => row.cells.length === columnCount);
  tools.querySelector("[data-table-count]").textContent = `${rows.length - 1} 件`;
  const checks = [...tools.querySelectorAll("input[data-column-index]")];
  const apply = () => {
    for (const check of checks) {
      for (const row of rows) row.cells[Number(check.dataset.columnIndex)].hidden = !check.checked;
    }
  };
  for (const check of checks) check.addEventListener("change", apply);
  tools.querySelector(".menu__reset").addEventListener("click", () => {
    for (const check of checks) check.checked = true;
    apply();
  });
}

// ===== コメント =====

const COMMENTS_KEY = "dev-comments";
// 引用を短くし始める字数と、短くした引用の先頭と末尾に残す字数
const QUOTE_MAX = 30;
const QUOTE_KEEP = 12;
// 通知を出しておく時間
const TOAST_MS = 2400;
// 選択の下に出すボタンの、画面の右端から離す幅
const ADD_BUTTON_ROOM = 160;

// コメントまわりの文言
const COMMENT_LABELS = {
  add: "コメントを追加",
  panel: "コメント",
  selectAll: "すべて選択（{selected} / {total}）",
  copy: "コピー",
  issue: "Issue を起票",
  empty: "コメントはありません",
  edit: "修正",
  delete: "削除",
  cancel: "キャンセル",
  save: "保存",
  submit: "追加",
  copied: "コピーしました",
  copyFailed: "コピーできませんでした",
  noSelection: "コメントを選択してください",
  required: "コメントを入力してください",
  jump: "見出しへ移動",
  open: "コメント（{count} 件）",
};

// モック専用: コメントの状態で見せる溜めたコメント
const SEEDS = {
  comments: [
    { file: "設定/開発ドキュメントサーバー", heading: "キー一覧", quote: "当たるパスなら読み書きをそのワークツリーへ向ける", body: "glob の記載例を追加してほしい。", selected: true },
    { file: "設定/開発ドキュメントサーバー", heading: "環境ごとの差分", quote: "config: [./dev-docs.yaml, ./dev-docs.local.yaml]", body: "後のファイルが上書きすることを本文にも記載する。", selected: false },
  ],
  "comments-local": [
    { file: "メモ/週次の振り返り", heading: "次にやること", quote: "議事録のテンプレートを決める", body: "期限を 11/7 にずらす。", selected: true },
  ],
};

const panel = document.getElementById("comment-panel");
const openButton = document.querySelector("[data-comment-open]");
const commentState = { draft: null, editing: null };

// モック専用: Git 管理外の配信元は GitHub のリポジトリを持たないため、Issue を起票できない
if (state === "comments-local") delete document.body.dataset.issueRepo;

/** 溜めたコメントを読む（無い・壊れているときは空） */
function loadComments() {
  try {
    const comments = JSON.parse(sessionStorage.getItem(COMMENTS_KEY) || "[]");
    return Array.isArray(comments) ? comments : [];
  } catch {
    return [];
  }
}

/** 溜めたコメントを書き、ボタンの数を描き直す */
function saveComments(comments) {
  sessionStorage.setItem(COMMENTS_KEY, JSON.stringify(comments));
  renderCommentButton(comments.length);
}

/** コメントのボタンの数と読み上げ名を、溜めた数に合わせる */
function renderCommentButton(count) {
  const badge = openButton.querySelector("[data-comment-count]");
  openButton.setAttribute("aria-label", COMMENT_LABELS.open.replace("{count}", String(count)));
  badge.textContent = String(count);
  badge.hidden = count === 0;
}

/** 文字列を HTML に入れられる形にする */
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** 選んだ文字列を引用の形にする（長ければ先頭と末尾だけを残す） */
function shortenQuote(text) {
  const flat = text.replace(/\s+/g, " ").trim();
  const graphemes = [...new Intl.Segmenter("ja", { granularity: "grapheme" }).segment(flat)].map((s) => s.segment);
  if (graphemes.length <= QUOTE_MAX) return flat;
  return `${graphemes.slice(0, QUOTE_KEEP).join("")} ... ${graphemes.slice(-QUOTE_KEEP).join("")}`;
}

/** コメントの場所の文言（文書のパスと直前の見出し） */
function formatLocation(comment) {
  return comment.heading ? `${comment.file} › ${comment.heading}` : comment.file;
}

/** 選んだ範囲より前にある最後の見出しを返す（無ければ null） */
function headingBefore(article, node) {
  return [...article.querySelectorAll("h2, h3")].filter((h) => h.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING).at(-1) ?? null;
}

/** 見出しの文言から、出ている本文の見出しの要素を引く */
function findHeading(text) {
  return [...(visibleArticle?.querySelectorAll("h2, h3") ?? [])].find((h) => h.textContent.trim() === text) ?? null;
}

/** 通知を画面の下に出す */
function showToast(text) {
  const toast = document.createElement("p");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.textContent = text;
  document.body.append(toast);
  setTimeout(() => toast.remove(), TOAST_MS);
}

/** コメント 1 つの HTML */
function commentItemHtml(comment) {
  const editing = commentState.editing === comment.id;
  // 修正中は入力欄と保存、それ以外は本文と修正・削除
  const body = editing
    ? `<textarea class="comment__input" rows="3" data-edit-body aria-label="${COMMENT_LABELS.panel}">${escapeHtml(comment.body)}</textarea>
       <p class="comment__error" hidden>${COMMENT_LABELS.required}</p>
       <div class="comment__actions">
         <button type="button" class="button" data-edit-cancel>${COMMENT_LABELS.cancel}</button>
         <button type="button" class="button button--primary" data-edit-save>${COMMENT_LABELS.save}</button>
       </div>`
    : `<p class="comment__body">${escapeHtml(comment.body)}</p>
       <div class="comment__actions">
         <button type="button" class="link-button" data-comment-edit>${COMMENT_LABELS.edit}</button>
         <button type="button" class="link-button" data-comment-delete>${COMMENT_LABELS.delete}</button>
       </div>`;
  return `
    <li class="comment" data-comment-id="${escapeHtml(comment.id)}">
      <div class="comment__head">
        <input type="checkbox" data-comment-check${comment.selected ? " checked" : ""} aria-label="選択">
        <span class="comment__place">${escapeHtml(formatLocation(comment))}</span>
        <button type="button" class="icon-button" data-comment-jump aria-label="${COMMENT_LABELS.jump}" title="${COMMENT_LABELS.jump}">
          <svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="m7.78 3.97 1.06-1.06a3.5 3.5 0 0 1 4.95 4.95l-2.5 2.5a3.5 3.5 0 0 1-4.95 0l.97-1.06a2 2 0 0 0 2.92-.01l2.5-2.5a2 2 0 0 0-2.83-2.83L8.84 5.03zm.44 8.06-1.06 1.06a3.5 3.5 0 0 1-4.95-4.95l2.5-2.5a3.5 3.5 0 0 1 4.95 0l-.97 1.06a2 2 0 0 0-2.92.01l-2.5 2.5a2 2 0 0 0 2.83 2.83l1.06-1.07z"/></svg>
        </button>
      </div>
      <blockquote class="comment__quote">${escapeHtml(comment.quote)}</blockquote>
      ${body}
    </li>`;
}

/** 溜めたコメントからパネルの中身を描き直す */
function renderCommentPanel() {
  const comments = loadComments();
  const draft = commentState.draft;
  const selected = comments.filter((c) => c.selected).length;
  // Issue の起票は GitHub のリポジトリを持つ配信元だけ
  const issue = document.body.dataset.issueRepo ? `<button type="button" class="button" data-comment-issue>${COMMENT_LABELS.issue}</button>` : "";
  const toolbar = comments.length === 0 ? "" : `
    <div class="comment-panel__toolbar">
      <label class="comment-panel__all"><input type="checkbox" data-comment-all> ${COMMENT_LABELS.selectAll.replace("{selected}", selected).replace("{total}", comments.length)}</label>
      <div class="comment-panel__actions">
        ${issue}
        <button type="button" class="button button--primary" data-comment-copy>${COMMENT_LABELS.copy}</button>
      </div>
    </div>`;
  const list = comments.length === 0 ? "" : `<ul class="comment-panel__list">${comments.map(commentItemHtml).join("")}</ul>`;
  // 書く枠は最後のコメントのすぐ下に置く
  const form = !draft ? "" : `
    <form class="comment comment--compose" data-comment-form novalidate>
      <p class="comment__place">${escapeHtml(formatLocation(draft))}</p>
      <blockquote class="comment__quote">${escapeHtml(draft.quote)}</blockquote>
      <textarea class="comment__input" rows="3" data-comment-body aria-label="${COMMENT_LABELS.panel}"></textarea>
      <p class="comment__error" hidden>${COMMENT_LABELS.required}</p>
      <div class="comment__actions">
        <button type="button" class="button" data-comment-cancel>${COMMENT_LABELS.cancel}</button>
        <button type="submit" class="button button--primary">${COMMENT_LABELS.submit}</button>
      </div>
    </form>`;
  const empty = comments.length === 0 && !draft ? `<p class="comment-panel__empty">${COMMENT_LABELS.empty}</p>` : "";
  panel.innerHTML = `
    <div class="comment-panel__head">
      <h2 class="comment-panel__title" tabindex="-1">${COMMENT_LABELS.panel}</h2>
      <button type="button" class="icon-button" data-comment-close aria-label="閉じる">
        <svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06"/></svg>
      </button>
    </div>
    <div class="comment-panel__body">${toolbar}${list}${form}${empty}</div>`;

  panel.querySelector("[data-comment-close]").addEventListener("click", closeCommentPanel);
  // すべて選択: 全てなら選んだ状態、一部なら途中の状態
  const all = panel.querySelector("[data-comment-all]");
  if (all) {
    all.checked = selected === comments.length;
    all.indeterminate = selected > 0 && selected < comments.length;
    all.addEventListener("change", () => {
      saveComments(loadComments().map((c) => ({ ...c, selected: all.checked })));
      renderCommentPanel();
    });
  }
  panel.querySelector("[data-comment-copy]")?.addEventListener("click", copyComments);
  panel.querySelector("[data-comment-issue]")?.addEventListener("click", openIssue);
  // コメントごとの操作
  for (const item of panel.querySelectorAll("[data-comment-id]")) {
    const id = item.dataset.commentId;
    item.querySelector("[data-comment-check]").addEventListener("change", (event) => {
      saveComments(loadComments().map((c) => (c.id === id ? { ...c, selected: event.target.checked } : c)));
      renderCommentPanel();
    });
    item.querySelector("[data-comment-jump]").addEventListener("click", () => {
      const comment = loadComments().find((c) => c.id === id);
      findHeading(comment.heading)?.scrollIntoView({ block: "start" });
    });
    item.querySelector("[data-comment-edit]")?.addEventListener("click", () => {
      commentState.editing = id;
      renderCommentPanel();
      panel.querySelector("[data-edit-body]").focus();
    });
    item.querySelector("[data-comment-delete]")?.addEventListener("click", () => {
      saveComments(loadComments().filter((c) => c.id !== id));
      renderCommentPanel();
    });
    item.querySelector("[data-edit-cancel]")?.addEventListener("click", () => {
      commentState.editing = null;
      renderCommentPanel();
    });
    item.querySelector("[data-edit-save]")?.addEventListener("click", () => {
      const input = item.querySelector("[data-edit-body]");
      if (!input.value.trim()) return showCommentError(input);
      commentState.editing = null;
      saveComments(loadComments().map((c) => (c.id === id ? { ...c, body: input.value.trim() } : c)));
      renderCommentPanel();
    });
  }
  // 書く枠のキャンセルと追加
  panel.querySelector("[data-comment-cancel]")?.addEventListener("click", () => {
    commentState.draft = null;
    renderCommentPanel();
  });
  panel.querySelector("[data-comment-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = panel.querySelector("[data-comment-body]");
    if (!input.value.trim()) return showCommentError(input);
    saveComments([...loadComments(), { ...draft, id: crypto.randomUUID(), body: input.value.trim(), selected: true }]);
    commentState.draft = null;
    renderCommentPanel();
  });
}

/** 入力チェックのエラーを入力欄の下に出す */
function showCommentError(input) {
  input.parentElement.querySelector(".comment__error").hidden = false;
  input.setAttribute("aria-invalid", "true");
  input.focus();
}

/** コメントのパネルを開く（書く枠の下書きがあれば書く枠を出す） */
function openCommentPanel(draft = null) {
  commentState.draft = draft;
  renderCommentPanel();
  panel.hidden = false;
  document.body.classList.add("is-comment-open");
  openButton.setAttribute("aria-expanded", "true");
  (panel.querySelector("[data-comment-body]") ?? panel.querySelector(".comment-panel__title")).focus({ preventScroll: true });
}

/** コメントのパネルを閉じる（溜めたコメントは残す） */
function closeCommentPanel() {
  panel.hidden = true;
  commentState.draft = null;
  commentState.editing = null;
  document.body.classList.remove("is-comment-open");
  openButton.setAttribute("aria-expanded", "false");
  openButton.focus();
}

/** 選んだコメントを一覧の順にまとめてクリップボードへ書く */
async function copyComments() {
  const selected = loadComments().filter((c) => c.selected);
  if (selected.length === 0) {
    showToast(COMMENT_LABELS.noSelection);
    return false;
  }
  const text = selected.map((c) => `${formatLocation(c)}\n> ${c.quote}\n\n${c.body}`).join("\n\n---\n\n");
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    showToast(COMMENT_LABELS.copyFailed);
    return false;
  }
  showToast(COMMENT_LABELS.copied);
  return true;
}

/** 選んだコメントをコピーしてから、GitHub の Issue の起票画面を別のタブで開く */
async function openIssue() {
  if (!(await copyComments())) return;
  const params = new URLSearchParams({ labels: document.body.dataset.issueLabels });
  window.open(`https://github.com/${document.body.dataset.issueRepo}/issues/new?${params}`, "_blank", "noopener");
}

if (panel) {
  // モック専用: コメントの状態では、溜めたコメントを入れてパネルを開いた状態で見せる
  if (SEEDS[state] && sessionStorage.getItem(`${COMMENTS_KEY}-seeded`) !== state) {
    saveComments(SEEDS[state].map((c) => ({ ...c, id: crypto.randomUUID() })));
    sessionStorage.setItem(`${COMMENTS_KEY}-seeded`, state);
  }
  renderCommentButton(loadComments().length);
  openButton.addEventListener("click", () => (panel.hidden ? openCommentPanel() : closeCommentPanel()));
  if (SEEDS[state]) openCommentPanel();

  // 本文の文字列を選んだときに、選択の下へ「コメントを追加」を出す
  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "button button--primary selection-comment";
  addButton.textContent = COMMENT_LABELS.add;
  addButton.hidden = true;
  document.body.append(addButton);
  let pending = null;
  document.addEventListener("selectionchange", () => {
    const selection = document.getSelection();
    const text = selection?.toString().trim();
    // 選択が空、または本文の外なら隠す
    if (!visibleArticle || !text || !selection.rangeCount || !visibleArticle.contains(selection.anchorNode)) {
      addButton.hidden = true;
      return;
    }
    // 場所と引用を控え、選択の下へボタンを置く
    const range = selection.getRangeAt(0);
    const fragment = range.cloneContents();
    fragment.querySelectorAll(".mdmark-anchor, .mdmark-visually-hidden").forEach((el) => el.remove());
    pending = { file: visibleArticle.dataset.docPath, heading: headingBefore(visibleArticle, range.startContainer)?.textContent.trim() ?? null, quote: shortenQuote(fragment.textContent) };
    const rect = range.getBoundingClientRect();
    addButton.style.top = `${window.scrollY + rect.bottom + 8}px`;
    addButton.style.left = `${window.scrollX + Math.max(8, Math.min(rect.left, window.innerWidth - ADD_BUTTON_ROOM))}px`;
    addButton.hidden = false;
  });
  // 押し下げで選択が外れないようにする
  addButton.addEventListener("mousedown", (event) => event.preventDefault());
  // Esc でボタンだけを隠す
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") addButton.hidden = true;
  });
  addButton.addEventListener("click", () => {
    addButton.hidden = true;
    openCommentPanel(pending);
    document.getSelection()?.removeAllRanges();
  });
}
