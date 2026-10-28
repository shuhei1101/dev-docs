/** 明暗の切り替え・配信元とリビジョンのメニュー・検索・通知（全ての画面が読む）。 */
import { readPageState } from "./state.js";
export const SCHEME_KEY = "dev-docs-color-scheme";
export const SEARCH_DEBOUNCE_MS = 200;
export const TOAST_MS = 2400;
/** `commandfor` を持たないブラウザだけ polyfill を読む。 */
async function loadInvokerPolyfill() {
    if (!("commandForElement" in HTMLButtonElement.prototype)) {
        await import("https://esm.run/invokers-polyfill");
    }
}
/** 通知を画面の下に `TOAST_MS` だけ出す。 */
export function showToast(text) {
    const toast = document.createElement("p");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.textContent = text;
    document.body.append(toast);
    setTimeout(() => toast.remove(), TOAST_MS);
}
/** 明暗の切り替え。システムの設定とその反対を切り替えて保存する。 */
export function initScheme() {
    const meta = document.querySelector('meta[name="color-scheme"]');
    const toggle = document.getElementById("scheme-toggle");
    if (!meta || !toggle)
        return;
    const systemDark = matchMedia("(prefers-color-scheme: dark)");
    const sync = () => toggle.setAttribute("aria-pressed", String(meta.content !== "light dark"));
    toggle.addEventListener("click", () => {
        try {
            if (meta.content === "light dark") {
                const opposite = systemDark.matches ? "light" : "dark";
                meta.content = opposite;
                document.documentElement.dataset.scheme = opposite;
                localStorage.setItem(SCHEME_KEY, opposite);
            }
            else {
                meta.content = "light dark";
                delete document.documentElement.dataset.scheme;
                localStorage.removeItem(SCHEME_KEY);
            }
        }
        catch {
            // 保存できなくても切り替えは効かせる
        }
        sync();
    });
    sync();
}
/** 文書のページのパスを URL の階層ごとに符号化する。 */
function encodePage(page) {
    return page.split("/").map(encodeURIComponent).join("/");
}
/** 配信元のトップの URL（リビジョンを指定しているときは `@ref` を付ける）。 */
function sourceBase(sourceId, ref) {
    return ref ? `/${sourceId}@${encodeURIComponent(ref)}` : `/${sourceId}`;
}
/** 配信元の切り替えのメニューを、画面の状態の `sources` で描く。 */
export function initSourceMenu(state) {
    const menu = document.querySelector("[data-source-menu]");
    if (!menu)
        return;
    const rows = (state.sources ?? []).map((source) => {
        const current = source.id === state.source_id ? ' aria-current="page"' : "";
        return `<a class="menu__item" href="/${encodeURIComponent(source.id)}/"${current}><span>${escapeText(source.id)}</span><span class="menu__note">${escapeText(source.note)}</span></a>`;
    });
    menu.insertAdjacentHTML("beforeend", `${rows.join("")}<a class="menu__item" href="/_settings/"><span>設定</span></a>`);
}
/** 文字列を HTML の本文に入れられる形にする。 */
function escapeText(text) {
    const element = document.createElement("span");
    element.textContent = text;
    return element.innerHTML;
}
/** `MM/DD HH:mm JST` の日時にする。 */
function formatJst(iso) {
    const parts = new Intl.DateTimeFormat("ja-JP", {
        timeZone: "Asia/Tokyo",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    }).formatToParts(new Date(iso));
    const value = (type) => parts.find((part) => part.type === type)?.value ?? "";
    return `${value("month")}/${value("day")} ${value("hour")}:${value("minute")} JST`;
}
/** 開いたときにリビジョンの一覧を取り、行のクリックでそのリビジョンの同じ文書を開く。 */
export function initRefMenu(state) {
    const menu = document.querySelector("[data-revision-menu]");
    if (!menu || !state.git || !state.source_id)
        return;
    const sourceId = state.source_id;
    const link = (ref, label, note) => {
        const base = sourceBase(sourceId, ref);
        const target = state.doc_page ? `${base}/${encodePage(state.doc_page)}` : `${base}/`;
        return `<a class="menu__item" href="${target}"><span class="mono">${escapeText(label)}</span><span class="menu__note">${escapeText(note)}</span></a>`;
    };
    let loaded = false;
    menu.addEventListener("toggle", async (event) => {
        if (event.newState !== "open" || loaded)
            return;
        loaded = true;
        try {
            const response = await fetch(`/_api/sources/${encodeURIComponent(sourceId)}/refs`);
            if (!response.ok)
                throw new Error(String(response.status));
            const refs = (await response.json());
            const rows = [link(null, refs.default_ref, "既定")];
            for (const branch of refs.branches ?? []) {
                if (branch.name !== refs.default_ref)
                    rows.push(link(branch.name, branch.name, "ブランチ"));
            }
            for (const tag of refs.tags ?? [])
                rows.push(link(tag.name, tag.name, "タグ"));
            for (const commit of refs.commits ?? []) {
                rows.push(link(commit.commit, commit.commit, formatJst(commit.date)));
            }
            menu.insertAdjacentHTML("beforeend", rows.join(""));
        }
        catch {
            loaded = false;
            menu.insertAdjacentHTML("beforeend", '<p class="menu__note" role="status">リビジョンを取得できませんでした</p>');
        }
    });
}
/** 検索のポップオーバーと `/` キー、入力ごとの検索と結果の描画。 */
export function initSearch(state) {
    const popover = document.getElementById("search");
    const input = document.getElementById("search-input");
    const count = document.querySelector("[data-search-count]");
    const results = document.querySelector("[data-search-results]");
    if (!popover || !input || !count || !results || !state.source_id)
        return;
    const sourceId = state.source_id;
    document.addEventListener("keydown", (event) => {
        const target = event.target;
        if (event.key === "/" && !target?.closest("input, textarea")) {
            event.preventDefault();
            popover.showPopover();
            input.focus();
        }
    });
    let timer;
    let controller;
    const search = async () => {
        const query = input.value.trim();
        controller?.abort();
        if (!query) {
            count.hidden = true;
            results.innerHTML = "";
            return;
        }
        controller = new AbortController();
        const params = new URLSearchParams({ q: query });
        if (state.ref_in_url)
            params.set("ref", state.ref_in_url);
        try {
            const response = await fetch(`/_api/sources/${encodeURIComponent(sourceId)}/search?${params}`, {
                signal: controller.signal,
            });
            if (!response.ok)
                throw new Error(String(response.status));
            const body = (await response.json());
            count.textContent = `${body.total_count} 件`;
            count.hidden = false;
            const base = sourceBase(sourceId, state.ref_in_url);
            results.innerHTML = body.items
                .map((item) => {
                const hit = item.snippets.map((line) => highlight(line, query)).join("<br>");
                return `<li><a href="${base}/${encodePage(item.path)}"><span class="search__path">${escapeText(item.name)}</span><span class="search__hit">${hit}</span></a></li>`;
            })
                .join("");
        }
        catch (error) {
            if (error.name !== "AbortError") {
                count.textContent = "検索できませんでした";
                count.hidden = false;
                results.innerHTML = "";
            }
        }
    };
    input.addEventListener("input", () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => void search(), SEARCH_DEBOUNCE_MS);
    });
}
/** 一致した行の語を強調する。 */
function highlight(line, query) {
    let html = escapeText(line);
    for (const word of query.split(/\s+/).filter(Boolean)) {
        const escaped = escapeText(word).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        html = html.replace(new RegExp(escaped, "gi"), (match) => `<mark>${match}</mark>`);
    }
    return html;
}
/** どの画面にも要る振る舞いを動かす。 */
export async function initShared() {
    await loadInvokerPolyfill();
    const state = readPageState();
    initScheme();
    initSourceMenu(state);
    initRefMenu(state);
    initSearch(state);
}
if (typeof document !== "undefined" && document.getElementById("page-state")) {
    void initShared();
}
