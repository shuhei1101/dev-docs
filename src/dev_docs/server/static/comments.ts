/** コメントの引用と起票画面の URL、コメントのパネル。 */

import type { PageState } from "./state.js";

export const COMMENTS_KEY = "dev-comments";
export const QUOTE_MAX = 30;
export const QUOTE_KEEP = 12;
export const ADD_BUTTON_ROOM = 160;
export const ISSUE_URL_MAX = 8000;
export const ISSUE_TRUNCATED =
  "\n\n…（長さの上限を超えたため、本文の末尾を切り詰めました。全文はクリップボードにコピーしています）";

export const COMMENT_LABELS = {
  add: "コメントを追加",
  empty: "コメントを入力してください",
  noSelection: "コメントを選んでください",
  copied: "コメントをコピーしました",
  copyFailed: "コピーできませんでした",
  panel: "コメント",
  selectAll: "すべて選択（{selected} / {total}）",
  copy: "コピー",
  issue: "Issue を起票",
  none: "コメントはありません",
  edit: "修正",
  delete: "削除",
  cancel: "キャンセル",
  save: "保存",
  submit: "追加",
  jump: "見出しへ移動",
  open: "コメント（{count} 件）",
} as const;

/** タブに溜める 1 件のコメント。 */
export type StoredComment = {
  id: string;
  file: string;
  heading: string | null;
  quote: string;
  body: string;
  selected: boolean;
};

/** 書き始めのコメント（場所と引用だけ）。 */
type Draft = Pick<StoredComment, "file" | "heading" | "quote">;

/** `QUOTE_MAX` を超える引用を先頭と末尾の `QUOTE_KEEP` 字と `…` にする。 */
export function shortenQuote(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  const graphemes = [...new Intl.Segmenter("ja", { granularity: "grapheme" }).segment(flat)].map(
    (part) => part.segment,
  );
  if (graphemes.length <= QUOTE_MAX) return flat;
  return `${graphemes.slice(0, QUOTE_KEEP).join("")}…${graphemes.slice(-QUOTE_KEEP).join("")}`;
}

/** 起票画面の URL を組み立てる。 */
function buildIssueUrl(repository: string, labels: string[], title: string, body: string): string {
  const params = new URLSearchParams({ title, body, labels: labels.join(",") });
  return `https://github.com/${repository}/issues/new?${params}`;
}

/** `ISSUE_URL_MAX` に収まるまで本文の末尾を切り詰めた起票画面の URL を返す。 */
export function fitIssueUrl(
  repository: string,
  labels: string[],
  title: string,
  body: string,
): string {
  const full = buildIssueUrl(repository, labels, title, body);
  if (full.length <= ISSUE_URL_MAX) return full;
  // 収まる本文の長さを二分探索で求める
  let low = 0;
  let high = body.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    const candidate = buildIssueUrl(repository, labels, title, body.slice(0, middle) + ISSUE_TRUNCATED);
    if (candidate.length <= ISSUE_URL_MAX) low = middle;
    else high = middle - 1;
  }
  return buildIssueUrl(repository, labels, title, body.slice(0, low) + ISSUE_TRUNCATED);
}

/** 選んだコメントを場所・引用・本文の順に区切り線でつなぐ。 */
export function formatComments(comments: StoredComment[]): string {
  return comments.map((c) => `${formatLocation(c)}\n> ${c.quote}\n\n${c.body}`).join("\n\n---\n\n");
}

/** コメントの場所の文言（文書のパスと直前の見出し）。 */
function formatLocation(comment: Draft): string {
  return comment.heading ? `${comment.file} › ${comment.heading}` : comment.file;
}

/** `sessionStorage` に溜めたコメントを読む（読めないときは空）。 */
export function loadComments(): StoredComment[] {
  try {
    const comments: unknown = JSON.parse(sessionStorage.getItem(COMMENTS_KEY) ?? "[]");
    return Array.isArray(comments) ? (comments as StoredComment[]) : [];
  } catch {
    return [];
  }
}

/** コメントを `sessionStorage` に書き、ボタンの数を描き直す。 */
export function saveComments(comments: StoredComment[]): void {
  try {
    sessionStorage.setItem(COMMENTS_KEY, JSON.stringify(comments));
  } catch {
    // 保存できなくても画面は動かす
  }
  renderCommentButton(comments.length);
}

/** コメントのボタンの数と読み上げ名を、溜めた数に合わせる。 */
function renderCommentButton(count: number): void {
  const button = document.querySelector<HTMLElement>("[data-comment-open]");
  const badge = button?.querySelector<HTMLElement>("[data-comment-count]");
  button?.setAttribute("aria-label", COMMENT_LABELS.open.replace("{count}", String(count)));
  if (badge) {
    badge.textContent = String(count);
    badge.hidden = count === 0;
  }
}

/** 文字列を HTML に入れられる形にする。 */
function escapeHtml(text: string): string {
  const entities: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return text.replace(/[&<>"']/g, (char) => entities[char] ?? char);
}

/** 通知を出す関数（共通の画面のスクリプトが渡す）。 */
export type Toast = (text: string) => void;

/** 選んだコメントをまとめてクリップボードへ書き、結果を通知する。 */
export async function copyComments(toast: Toast): Promise<boolean> {
  const selected = loadComments().filter((c) => c.selected);
  if (selected.length === 0) {
    toast(COMMENT_LABELS.noSelection);
    return false;
  }
  try {
    await navigator.clipboard.writeText(formatComments(selected));
  } catch {
    toast(COMMENT_LABELS.copyFailed);
    return false;
  }
  toast(COMMENT_LABELS.copied);
  return true;
}

/** 選んだコメントをコピーしてから、起票画面を別のタブで開く。 */
export async function openIssue(state: PageState, toast: Toast): Promise<void> {
  if (!state.github_repository) return;
  if (!(await copyComments(toast))) return;
  const selected = loadComments().filter((c) => c.selected);
  const title = [...new Set(selected.map((c) => c.file))].join("、");
  const url = fitIssueUrl(state.github_repository, state.issue_labels, title, formatComments(selected));
  window.open(url, "_blank", "noopener");
}

/** 選んだ範囲より前にある最後の見出しを返す。 */
function headingBefore(article: HTMLElement, node: Node): HTMLElement | null {
  const headings = [...article.querySelectorAll<HTMLElement>("h2, h3")].filter(
    (heading) => heading.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING,
  );
  return headings.at(-1) ?? null;
}

/** 見出しの文言から、本文の見出しの要素を引く。 */
function findHeading(article: HTMLElement | null, text: string | null): HTMLElement | null {
  if (!article || !text) return null;
  return (
    [...article.querySelectorAll<HTMLElement>("h2, h3")].find(
      (heading) => heading.textContent?.trim() === text,
    ) ?? null
  );
}

const ICON_LINK =
  '<svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="m7.78 3.97 1.06-1.06a3.5 3.5 0 0 1 4.95 4.95l-2.5 2.5a3.5 3.5 0 0 1-4.95 0l.97-1.06a2 2 0 0 0 2.92-.01l2.5-2.5a2 2 0 0 0-2.83-2.83L8.84 5.03zm.44 8.06-1.06 1.06a3.5 3.5 0 0 1-4.95-4.95l2.5-2.5a3.5 3.5 0 0 1 4.95 0l-.97 1.06a2 2 0 0 0-2.92.01l-2.5 2.5a2 2 0 0 0 2.83 2.83l1.06-1.07z"/></svg>';
const ICON_CLOSE =
  '<svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06"/></svg>';

/** コメントのパネルの状態（書きかけと修正中）。 */
type PanelState = { draft: Draft | null; editing: string | null };

/** コメント 1 つの HTML。 */
function commentItemHtml(comment: StoredComment, editing: boolean): string {
  const body = editing
    ? `<textarea class="comment__input" rows="3" data-edit-body aria-label="${COMMENT_LABELS.panel}">${escapeHtml(comment.body)}</textarea>
       <p class="comment__error" hidden>${COMMENT_LABELS.empty}</p>
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
        <button type="button" class="icon-button" data-comment-jump aria-label="${COMMENT_LABELS.jump}" title="${COMMENT_LABELS.jump}">${ICON_LINK}</button>
      </div>
      <blockquote class="comment__quote">${escapeHtml(comment.quote)}</blockquote>
      ${body}
    </li>`;
}

/** 入力チェックのエラーを入力欄の下に出す。 */
function showCommentError(input: HTMLTextAreaElement): void {
  const error = input.parentElement?.querySelector<HTMLElement>(".comment__error");
  if (error) error.hidden = false;
  input.setAttribute("aria-invalid", "true");
  input.focus();
}

/** 選択の下のコメントを追加ボタン・パネルの開閉・追加・修正・削除・選択を組む。 */
export function initCommentPanel(state: PageState, toast: Toast): void {
  const panel = document.getElementById("comment-panel");
  const openButton = document.querySelector<HTMLElement>("[data-comment-open]");
  const article = document.querySelector<HTMLElement>("article.markdown-body");
  if (!panel || !openButton) return;
  const view: PanelState = { draft: null, editing: null };

  const render = (): void => {
    const comments = loadComments();
    const selected = comments.filter((c) => c.selected).length;
    const issue = state.github_repository
      ? `<button type="button" class="button" data-comment-issue>${COMMENT_LABELS.issue}</button>`
      : "";
    const label = COMMENT_LABELS.selectAll
      .replace("{selected}", String(selected))
      .replace("{total}", String(comments.length));
    const toolbar =
      comments.length === 0
        ? ""
        : `<div class="comment-panel__toolbar">
            <label class="comment-panel__all"><input type="checkbox" data-comment-all> ${label}</label>
            <div class="comment-panel__actions">${issue}
              <button type="button" class="button button--primary" data-comment-copy>${COMMENT_LABELS.copy}</button>
            </div>
          </div>`;
    const list =
      comments.length === 0
        ? ""
        : `<ul class="comment-panel__list">${comments
            .map((c) => commentItemHtml(c, view.editing === c.id))
            .join("")}</ul>`;
    const draft = view.draft;
    const form = draft
      ? `<form class="comment comment--compose" data-comment-form novalidate>
          <p class="comment__place">${escapeHtml(formatLocation(draft))}</p>
          <blockquote class="comment__quote">${escapeHtml(draft.quote)}</blockquote>
          <textarea class="comment__input" rows="3" data-comment-body aria-label="${COMMENT_LABELS.panel}"></textarea>
          <p class="comment__error" hidden>${COMMENT_LABELS.empty}</p>
          <div class="comment__actions">
            <button type="button" class="button" data-comment-cancel>${COMMENT_LABELS.cancel}</button>
            <button type="submit" class="button button--primary">${COMMENT_LABELS.submit}</button>
          </div>
        </form>`
      : "";
    const empty =
      comments.length === 0 && !draft
        ? `<p class="comment-panel__empty">${COMMENT_LABELS.none}</p>`
        : "";
    panel.innerHTML = `
      <div class="comment-panel__head">
        <h2 class="comment-panel__title" tabindex="-1">${COMMENT_LABELS.panel}</h2>
        <button type="button" class="icon-button" data-comment-close aria-label="閉じる">${ICON_CLOSE}</button>
      </div>
      <div class="comment-panel__body">${toolbar}${list}${form}${empty}</div>`;
    wire(comments, selected);
  };

  const wire = (comments: StoredComment[], selected: number): void => {
    panel.querySelector("[data-comment-close]")?.addEventListener("click", close);
    const all = panel.querySelector<HTMLInputElement>("[data-comment-all]");
    if (all) {
      all.checked = selected === comments.length;
      all.indeterminate = selected > 0 && selected < comments.length;
      all.addEventListener("change", () => {
        saveComments(loadComments().map((c) => ({ ...c, selected: all.checked })));
        render();
      });
    }
    panel
      .querySelector("[data-comment-copy]")
      ?.addEventListener("click", () => void copyComments(toast));
    panel
      .querySelector("[data-comment-issue]")
      ?.addEventListener("click", () => void openIssue(state, toast));
    for (const item of panel.querySelectorAll<HTMLElement>("[data-comment-id]")) {
      const id = item.dataset.commentId ?? "";
      item.querySelector<HTMLInputElement>("[data-comment-check]")?.addEventListener("change", (event) => {
        const checked = (event.target as HTMLInputElement).checked;
        saveComments(loadComments().map((c) => (c.id === id ? { ...c, selected: checked } : c)));
        render();
      });
      item.querySelector("[data-comment-jump]")?.addEventListener("click", () => {
        const comment = loadComments().find((c) => c.id === id);
        findHeading(article, comment?.heading ?? null)?.scrollIntoView({ block: "start" });
      });
      item.querySelector("[data-comment-edit]")?.addEventListener("click", () => {
        view.editing = id;
        render();
        panel.querySelector<HTMLTextAreaElement>("[data-edit-body]")?.focus();
      });
      item.querySelector("[data-comment-delete]")?.addEventListener("click", () => {
        saveComments(loadComments().filter((c) => c.id !== id));
        render();
      });
      item.querySelector("[data-edit-cancel]")?.addEventListener("click", () => {
        view.editing = null;
        render();
      });
      item.querySelector("[data-edit-save]")?.addEventListener("click", () => {
        const input = item.querySelector<HTMLTextAreaElement>("[data-edit-body]");
        if (!input) return;
        if (!input.value.trim()) return showCommentError(input);
        view.editing = null;
        saveComments(loadComments().map((c) => (c.id === id ? { ...c, body: input.value.trim() } : c)));
        render();
      });
    }
    panel.querySelector("[data-comment-cancel]")?.addEventListener("click", () => {
      view.draft = null;
      render();
    });
    panel.querySelector("[data-comment-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = panel.querySelector<HTMLTextAreaElement>("[data-comment-body]");
      if (!input || !view.draft) return;
      if (!input.value.trim()) return showCommentError(input);
      saveComments([
        ...loadComments(),
        { ...view.draft, id: crypto.randomUUID(), body: input.value.trim(), selected: true },
      ]);
      view.draft = null;
      render();
    });
  };

  const open = (draft: Draft | null = null): void => {
    view.draft = draft;
    render();
    panel.hidden = false;
    document.body.classList.add("is-comment-open");
    openButton.setAttribute("aria-expanded", "true");
    const target =
      panel.querySelector<HTMLElement>("[data-comment-body]") ??
      panel.querySelector<HTMLElement>(".comment-panel__title");
    target?.focus({ preventScroll: true });
  };

  function close(): void {
    panel!.hidden = true;
    view.draft = null;
    view.editing = null;
    document.body.classList.remove("is-comment-open");
    openButton!.setAttribute("aria-expanded", "false");
    openButton!.focus();
  }

  renderCommentButton(loadComments().length);
  openButton.addEventListener("click", () => (panel.hidden ? open() : close()));
  if (article) initSelectionButton(article, state, open);
}

/** 本文の文字列を選んだときに、選択の下へ「コメントを追加」を出す。 */
function initSelectionButton(
  article: HTMLElement,
  state: PageState,
  open: (draft: Draft) => void,
): void {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button button--primary selection-comment";
  button.textContent = COMMENT_LABELS.add;
  button.hidden = true;
  document.body.append(button);
  let pending: Draft | null = null;
  document.addEventListener("selectionchange", () => {
    const selection = document.getSelection();
    const text = selection?.toString().trim();
    // 選択が空、または本文の外なら隠す
    if (!selection || !text || !selection.rangeCount || !article.contains(selection.anchorNode)) {
      button.hidden = true;
      return;
    }
    const range = selection.getRangeAt(0);
    const fragment = range.cloneContents();
    fragment.querySelectorAll(".mdmark-anchor, .mdmark-visually-hidden").forEach((el) => el.remove());
    pending = {
      file: state.doc_page ?? "",
      heading: headingBefore(article, range.startContainer)?.textContent?.trim() ?? null,
      quote: shortenQuote(fragment.textContent ?? ""),
    };
    const rect = range.getBoundingClientRect();
    button.style.top = `${window.scrollY + rect.bottom + 8}px`;
    button.style.left = `${window.scrollX + Math.max(8, Math.min(rect.left, window.innerWidth - ADD_BUTTON_ROOM))}px`;
    button.hidden = false;
  });
  // 押し下げで選択が外れないようにする
  button.addEventListener("mousedown", (event) => event.preventDefault());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") button.hidden = true;
  });
  button.addEventListener("click", () => {
    button.hidden = true;
    if (pending) open(pending);
    document.getSelection()?.removeAllRanges();
  });
}
