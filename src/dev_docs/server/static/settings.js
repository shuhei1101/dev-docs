/** 設定画面の一覧と、追加・編集・削除のダイアログ。 */
import { showToast } from "./shared.js";
import { readPageState } from "./state.js";
/** 空の `id`・`scope.read`・`scope.write` は送らず、`sources[]` の全行を保存する。 */
export async function putSources(sources) {
    const body = sources.map((entry) => {
        const scope = {};
        if (entry.scope.read.length)
            scope.read = entry.scope.read;
        if (entry.scope.write?.length)
            scope.write = entry.scope.write;
        return {
            ...(entry.id ? { id: entry.id } : {}),
            config: entry.config,
            enabled: entry.enabled,
            ...(Object.keys(scope).length ? { scope } : {}),
        };
    });
    const response = await fetch("/_api/settings/sources", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: body }),
    });
    if (response.ok) {
        const result = (await response.json());
        return { ok: true, sources: result.sources };
    }
    try {
        const problem = (await response.json());
        return { ok: false, errors: problem.errors ?? [{ path: "$", reason: problem.detail ?? String(response.status) }] };
    }
    catch {
        return { ok: false, errors: [{ path: "$", reason: String(response.status) }] };
    }
}
/** 文字列を HTML の本文に入れられる形にする。 */
function escapeText(text) {
    const element = document.createElement("span");
    element.textContent = text;
    return element.innerHTML;
}
/** 1 行 1 値の入力を値の並びにする（末尾の改行は無視する）。 */
function lines(text) {
    return text.replace(/\n+$/, "").split("\n");
}
/** 入力欄が空なら空の並びにする。 */
function linesOrEmpty(text) {
    return text.trim() === "" ? [] : lines(text);
}
/** 状態の表示（バッジと補足）を作る。 */
function statusHtml(row) {
    if (row.status === "not_served") {
        const detail = (row.errors ?? [])
            .map((error) => `<code>${escapeText(error.path)}</code>: ${escapeText(error.reason)}`)
            .join("、");
        return `<span class="status status--error">配信していません</span><span class="status-note">起動時の検証で外しました（${detail}）</span>`;
    }
    if (row.status === "disabled" || row.enabled === false) {
        return '<span class="status status--muted">無効</span><span class="status-note"><code>enabled</code> が <code>false</code> です</span>';
    }
    const old = row.config_version
        ? `<span class="status-note"><code>dev-docs.yaml</code> の <code>version</code> が古い ${escapeText(row.config_version.config)} です。このサーバーが読むのは ${escapeText(row.config_version.server)} です</span>`
        : "";
    return `<span class="status status--ok">配信中</span>${old}`;
}
/** 設定画面の一覧と、追加・編集・削除のダイアログを組む。 */
export function initSettings() {
    const state = readPageState();
    let rows = state.sources ?? [];
    const body = document.querySelector("[data-sources-body]");
    const count = document.querySelector("[data-sources-count]");
    const dialog = document.getElementById("source-dialog");
    const form = document.querySelector("[data-source-form]");
    const removeDialog = document.getElementById("delete-dialog");
    const removeForm = document.querySelector("[data-delete-form]");
    if (!body || !count || !dialog || !form || !removeDialog || !removeForm)
        return;
    const field = (id) => document.getElementById(id);
    let editing = null;
    let deleting = null;
    const entries = () => rows.map(({ id, config, enabled, scope }) => ({ id, config, enabled, scope }));
    const render = () => {
        count.textContent = `配信元 ${rows.length} 件`;
        body.innerHTML = rows
            .map((row, index) => {
            const name = row.id ?? "";
            const label = row.status === "serving" && name ? `<a href="/${encodeURIComponent(name)}/">${escapeText(name)}</a>` : `<code>${escapeText(name)}</code>`;
            const configs = row.config.map((path) => `<code>${escapeText(path)}</code>`).join("<br>");
            return `<tr>
          <td>${label}</td>
          <td class="col-config">${configs}</td>
          <td class="col-status">${statusHtml(row)}</td>
          <td class="col-actions">
            <button class="tool-button" type="button" data-edit="${index}" aria-label="${escapeText(name)} を編集">編集</button>
            <button class="tool-button tool-button--danger" type="button" data-remove="${index}" aria-label="${escapeText(name)} を削除">削除</button>
          </td>
        </tr>`;
        })
            .join("");
    };
    const clearErrors = () => {
        form.querySelector("[data-error-summary]").hidden = true;
        form.querySelector("[data-error-list]").innerHTML = "";
        for (const error of form.querySelectorAll(".field__error"))
            error.hidden = true;
        for (const wrapper of form.querySelectorAll(".field"))
            wrapper.classList.remove("is-invalid");
        for (const input of form.querySelectorAll("[aria-invalid]"))
            input.removeAttribute("aria-invalid");
    };
    const openForm = (index) => {
        editing = index;
        clearErrors();
        const row = index === null ? null : rows[index];
        document.getElementById("source-dialog-title").textContent = row ? `${row.id ?? ""} を編集` : "配信元を追加";
        const idInput = field("source-id");
        const fixed = form.querySelector("[data-id-fixed]");
        idInput.value = row?.id ?? "";
        idInput.hidden = Boolean(row);
        fixed.hidden = !row;
        fixed.textContent = row?.id ?? "";
        field("source-config").value = (row?.config ?? []).join("\n");
        field("source-enabled").checked = row?.enabled ?? true;
        field("source-read").value = (row?.scope.read ?? []).join("\n");
        field("source-write").value = (row?.scope.write ?? []).join("\n");
        form.querySelector("[data-dialog-submit]").textContent = row ? "保存" : "追加";
        dialog.showModal();
    };
    /** 保存の失敗を、まとめと入力欄の下に出す。 */
    const showErrors = (errors) => {
        clearErrors();
        const summary = form.querySelector("[data-error-summary]");
        form.querySelector("[data-error-title]").textContent = `保存できませんでした。${errors.length} 件の項目がスキーマに合いません。`;
        const list = form.querySelector("[data-error-list]");
        const targets = { id: "id", config: "config", "scope.read": "read", "scope.write": "write" };
        for (const error of errors) {
            const key = error.path.replace(/^sources\[\d+\]\.?/, "").replace(/\[\d+\]$/, "");
            const name = targets[key];
            const item = document.createElement("li");
            item.innerHTML = `<code>${escapeText(error.path)}</code>: ${escapeText(error.reason)}`;
            list.append(item);
            if (!name)
                continue;
            const wrapper = form.querySelector(`[data-field="${name}"]`);
            const message = wrapper?.querySelector(".field__error");
            const input = wrapper?.querySelector(".field__input");
            wrapper?.classList.add("is-invalid");
            if (message) {
                message.textContent = error.reason;
                message.hidden = false;
                input?.setAttribute("aria-invalid", "true");
                input?.setAttribute("aria-describedby", `${input.getAttribute("aria-describedby") ?? ""} ${message.id}`.trim());
            }
        }
        summary.hidden = false;
    };
    /** 今の一覧に入力を反映した `sources[]` を送り、応答の状態で一覧を描き直す。 */
    const save = async (next) => {
        const result = await putSources(next);
        if (!result.ok)
            return result.errors;
        rows = next.map((entry, index) => ({ ...entry, ...(result.sources[index] ?? {}), id: entry.id ?? result.sources[index]?.id }));
        render();
        return null;
    };
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const entry = {
            id: editing === null ? (field("source-id").value.trim() || undefined) : rows[editing].id,
            config: linesOrEmpty(field("source-config").value),
            enabled: field("source-enabled").checked,
            scope: { read: linesOrEmpty(field("source-read").value), write: linesOrEmpty(field("source-write").value) },
        };
        const next = entries();
        if (editing === null)
            next.push(entry);
        else
            next[editing] = entry;
        const index = editing === null ? next.length - 1 : editing;
        const errors = await save(next);
        if (errors) {
            // 保存の失敗の位置は、送った一覧の中の位置なので、この行の位置に読み替える
            showErrors(errors.map((error) => ({ ...error, path: error.path.replace(/^sources\[\d+\]/, `sources[${index}]`) })));
            return;
        }
        dialog.close();
    });
    removeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (deleting === null)
            return;
        const next = entries().filter((_, index) => index !== deleting);
        const errors = await save(next);
        if (errors) {
            removeForm.querySelector("[data-delete-error]").hidden = false;
            removeForm.querySelector("[data-delete-error-text]").textContent = `削除できませんでした（${errors.map((e) => e.reason).join("、")}）`;
            return;
        }
        removeDialog.close();
        showToast("削除しました");
    });
    for (const button of document.querySelectorAll("[data-dialog-cancel]")) {
        button.addEventListener("click", () => button.closest("dialog")?.close());
    }
    document.querySelector("[data-source-add]")?.addEventListener("click", () => openForm(null));
    body.addEventListener("click", (event) => {
        const target = event.target.closest("[data-edit], [data-remove]");
        if (!target)
            return;
        if (target.dataset.edit !== undefined) {
            openForm(Number(target.dataset.edit));
        }
        else {
            deleting = Number(target.dataset.remove);
            const row = rows[deleting];
            document.getElementById("delete-dialog-title").textContent = `${row.id ?? ""} を削除しますか？`;
            removeForm.querySelector("[data-delete-text]").innerHTML = `端末の設定から <code>${escapeText(row.id ?? "")}</code> の行を削除し、配信を止めます。配信元のフォルダと文書は削除しません。`;
            removeForm.querySelector("[data-delete-error]").hidden = true;
            removeDialog.showModal();
        }
    });
    render();
    // 戻るリンクは、開いていた配信元のトップへ（無ければ先頭の配信中の配信元）
    const back = document.querySelector("[data-back-link]");
    const serving = rows.find((row) => row.status === "serving");
    if (back && serving?.id) {
        back.href = `/${encodeURIComponent(serving.id)}/`;
        back.querySelector("[data-back-label]").textContent = `${serving.id} のトップへ戻る`;
    }
    else if (back) {
        back.hidden = true;
    }
}
initSettings();
