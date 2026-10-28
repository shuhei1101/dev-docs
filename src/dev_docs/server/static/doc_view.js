/** 文書の画面の本文の描画・目次・表の件数と列の表示。 */
import { initCommentPanel } from "./comments.js";
import { showToast } from "./shared.js";
import { readPageState } from "./state.js";
/** 本文の Markdown を mdmark で描き、差分の元があれば差分を強調する。 */
export async function renderBody(state) {
    const article = document.querySelector("article.markdown-body");
    if (!article)
        return null;
    const url = document.body.dataset.mdmarkUrl ?? "";
    let mdmark;
    try {
        mdmark = (await import(url));
    }
    catch (error) {
        console.error(`mdmark を読み込めませんでした: ${url}`, error);
        return null;
    }
    const markdown = article.querySelector("textarea[data-mdmark-source]")?.value ?? "";
    const previous = article.querySelector("textarea[data-mdmark-diff-source]")?.value;
    const diff = state.diff;
    if (previous !== undefined && diff) {
        const contents = { current: markdown, previous };
        const diffSource = {
            revisions: async () => [
                { id: "current", at: diff.current_date, label: diff.current_commit },
                { id: "previous", at: diff.date, label: diff.commit },
            ],
            content: async ({ revisionId }) => contents[revisionId] ?? "",
        };
        await mdmark.mount(article, { markdown, diffSource, docId: article.dataset.docPath });
    }
    else {
        await mdmark.mount(article, { markdown });
    }
    buildToc(article);
    initColumns(article, state);
    return article;
}
/** 本文の `h2[id]` から右の目次と本文の上の目次を作る。 */
export function buildToc(article) {
    const headings = [...article.querySelectorAll("h2[id]")];
    for (const list of document.querySelectorAll("[data-toc-list]")) {
        const sidebar = Boolean(list.closest(".toc"));
        list.innerHTML = "";
        for (const heading of headings) {
            const item = document.createElement("li");
            const anchor = document.createElement("a");
            anchor.href = `#${encodeURIComponent(heading.id)}`;
            anchor.textContent = heading.textContent?.trim() ?? "";
            item.append(anchor);
            list.append(item);
        }
        if (sidebar)
            observeHeadings(list, headings);
    }
}
/** 右の目次の、今いる見出しに `aria-current="location"` を付ける。 */
function observeHeadings(list, headings) {
    const anchors = [...list.querySelectorAll("a")];
    const mark = (index) => {
        anchors.forEach((anchor, position) => {
            anchor.classList.toggle("is-current", position === index);
            if (position === index)
                anchor.setAttribute("aria-current", "location");
            else
                anchor.removeAttribute("aria-current");
        });
    };
    mark(0);
    const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (entry.isIntersecting)
                mark(headings.indexOf(entry.target));
        }
    }, { rootMargin: "0px 0px -70% 0px" });
    for (const heading of headings)
        observer.observe(heading);
}
/** 表の列の設定を保存する。失敗したら通知で知らせる。 */
export async function saveColumns(source, table, hidden) {
    try {
        const response = await fetch(`/_api/sources/${encodeURIComponent(source)}/columns`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ table, hidden }),
        });
        if (!response.ok)
            throw new Error(String(response.status));
    }
    catch {
        showToast("列の設定を保存できませんでした");
    }
}
const ICON_COLUMNS = '<svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16"><path d="M1.75 2h12.5c.41 0 .75.34.75.75v10.5a.75.75 0 0 1-.75.75H1.75a.75.75 0 0 1-.75-.75V2.75c0-.41.34-.75.75-.75M2.5 3.5v9h3v-9zm4.5 0v9h2v-9zm3.5 0v9h3v-9z"/></svg>';
/** 本文の表の前に件数と列の表示を置き、隠す列を当てて保存する。 */
export function initColumns(article, state) {
    const tables = [...article.querySelectorAll("table")];
    // 数が合わない表はキーを持たせず、件数だけ出す
    const keyed = tables.length === state.table_keys.length;
    tables.forEach((table, index) => {
        const header = table.tHead?.rows[0];
        if (!header)
            return;
        const columnCount = header.cells.length;
        // 行の詳細の行は除き、見出しの行と同じ数のセルを持つ行だけを対象にする
        const rows = [...table.rows].filter((row) => row.cells.length === columnCount);
        const key = keyed ? state.table_keys[index] : undefined;
        const names = [...header.cells].map((cell) => cell.textContent?.trim() ?? "");
        const hidden = new Set(key ? (state.hidden_columns[key] ?? []) : []);
        const menuId = `columns-menu-${index}`;
        const tools = document.createElement("div");
        tools.className = "table-tools";
        const checks = names
            .map((name, column) => `<label class="menu__check"><input type="checkbox" data-column-index="${column}"${hidden.has(name) ? "" : " checked"}${column === 0 ? " disabled" : ""}> <span></span></label>`)
            .join("");
        tools.innerHTML = `<span class="table-tools__count">${rows.length - 1} 件</span>${key
            ? `<button class="tool-button" type="button" commandfor="${menuId}" command="toggle-popover">${ICON_COLUMNS}列の表示</button>
           <div id="${menuId}" class="menu" popover><p class="menu__heading">表示する列</p>${checks}<button class="menu__reset" type="button">既定に戻す</button></div>`
            : ""}`;
        const labels = tools.querySelectorAll(".menu__check span");
        labels.forEach((label, column) => (label.textContent = names[column] ?? ""));
        (table.closest(".mdmark-table") ?? table).before(tools);
        if (!key)
            return;
        const inputs = [...tools.querySelectorAll("input[data-column-index]")];
        const apply = () => {
            for (const input of inputs) {
                for (const row of rows)
                    row.cells[Number(input.dataset.columnIndex)].hidden = !input.checked;
            }
        };
        const save = () => {
            const list = inputs.filter((input) => !input.checked).map((input) => names[Number(input.dataset.columnIndex)]);
            void saveColumns(state.source_id ?? "", key, list);
        };
        for (const input of inputs) {
            input.addEventListener("change", () => {
                apply();
                save();
            });
        }
        tools.querySelector(".menu__reset")?.addEventListener("click", () => {
            for (const input of inputs)
                input.checked = true;
            apply();
            save();
        });
        apply();
    });
}
const state = readPageState();
void renderBody(state);
initCommentPanel(state, showToast);
