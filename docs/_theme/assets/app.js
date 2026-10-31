"use strict";
/* ============================================================================
 * ai-monitor ドキュメントサイト 共通スクリプト
 *
 * docs/ 配下すべてのページで読み込む単一 JS。
 * 各機能は「対象 DOM が無ければ何もしない」形で並べており、
 * Mock demo / Jekyll 描画ページ / 公開ドキュメントなど、ページ種別を問わず同じファイルで動く。
 * 上タブの生成だけは _layouts/default.html の Liquid が担う（ここでは扱わない）。
 *
 * 本文の Markdown → HTML の変換は Jekyll 側で完了している。ここで変換するのは言語指定が markdown のコードブロックの中身だけ。
 *
 * 提供する機能:
 *   1.  パンくずリスト     ... [data-breadcrumb] があれば URL 階層から自動生成
 *   2.  表の種類と機能     ... 範囲のコメントで包んだ表に、種類ごとにピン留め・並べ替え・絞り込み・件数・列の表示・列の値の絞り込み・集計行を付ける
 *   3.  見出しアンカー     ... h2-h4 に # リンクを追加、クリックで URL をコピー
 *   4.  コードコピー       ... pre 右上のコピーボタン
 *   5.  コールアウト       ... GitHub Alert 記法の引用に種別の class を付ける
 *   6.  表の横スクロール   ... table を .table-frame と .table-wrap の二重で包み、列数の多い表は最終列を畳む。列のピン留めと見出し行の追従を付ける
 *   7.  Mermaid 描画・拡大 ... code.language-mermaid をレンダリングし、押下で全画面拡大
 *   8.  目次               ... [data-toc] に h2/h3 を並べ、現在位置ハイライト
 *   9.  サイドバー         ... [data-sidebar-source] の目次表からセクション別に生成
 *   10. ドロワー・幅の切り替え ... 720px / 960px でサイドバー・目次の配置を切り替える
 *   11. ダークモード切替   ... [data-theme-toggle] で light/dark 切替、localStorage 保存
 *   12. コード言語ラベル   ... pre 左上に言語名を表示
 *   13. 見出し単位の検索   ... /search.json をロードして検索モーダルで見出し単位に絞り込み
 *   14. 起票               ... 読んでいるページから Issue の下書きを作り、GitHub の起票画面を開く
 *   15. トップに戻る       ... [data-back-to-top] のボタンをスクロール量で表示切替
 *   16. Mock demo 用       ... 検索・行クリック・新規追加・編集モード・トースト
 *   17. コード内の Markdown ... markdown のコードブロックの中身を描き、元のコードとの切り替えを付ける
 *   18. 図の埋め込み       ... 段落にリンク 1 本だけを置いた位置へ、リンク先の見出しの下の図を置く
 *   19. リビジョンと差分         ... 開発ドキュメントサーバーのリビジョンバー・差分と全文の切り替え・変更の量・図の変更のマーク・基準を保つリンク
 *   20. 設計書の表示       ... 開発ドキュメントサーバーの Schema のタブ・表の件数・項目の要点パネル
 *   21. 列の表示           ... 開発ドキュメントサーバーの表示する列のメニューと列の組の保存
 *   22. コメント           ... 開発ドキュメントサーバーの選んだ文字列へのコメント・行のマーク・まとめてのコピーと起票
 *   23. 行の詳細           ... 開発ドキュメントサーバーの表の行の開閉・すべて開く・大きな値の全体
 * ============================================================================ */
/* ---------- 定数 ---------- */
const TOAST_DISPLAY_MS = 1800;
const BACK_TO_TOP_THRESHOLD_PX = 300;
const MOBILE_WIDTH = 720;
const TOC_INLINE_WIDTH = 960;
const mobileQuery = window.matchMedia(`(max-width: ${MOBILE_WIDTH}px)`);
const tocInlineQuery = window.matchMedia(`(max-width: ${TOC_INLINE_WIDTH}px)`);
/* 幅の切り替えで動かすナビゲーションの要素への参照と、開いているドロワーを閉じる手段 */
const layout = { nav: null, toc: null, tocInline: null, tocAside: null, article: null, closeDrawer: null };
/* パンくず階層のラベル辞書。URL セグメント → 表示名。未登録は素通し。 */
const BREADCRUMB_LABELS = {
    "": "トップ",
    "docs": "ドキュメント",
    "mock": "モック",
    "pages": "画面",
    "components": "コンポーネント",
    "styles": "スタイル",
    "issues": "Issue",
    "assets": "アセット",
};
/* ============================================================================
 * 1. パンくずリスト
 * ---------------------------------------------------------------------------- */
/** ルート（末尾スラッシュ付き）とパス配下のセグメントに分割する */
function splitPathBySiteRoot() {
    // _layouts/default.html が data-site-root="{{ '/' | relative_url }}" を注入する
    // GitHub Pages（project pages）だと "/ai-monitor/"、ローカルルート配信だと "/"
    const bodyRoot = document.body?.dataset?.siteRoot || "/";
    const siteRoot = bodyRoot.endsWith("/") ? bodyRoot : bodyRoot + "/";
    const pathname = decodeURIComponent(window.location.pathname);
    // 末尾のファイル名を落として必ずディレクトリ形にする
    const dir = pathname.endsWith("/") ? pathname : pathname.replace(/\/[^\/]*$/, "/");
    // site root 直下の相対パスを取り出す
    const rel = dir.startsWith(siteRoot) ? dir.slice(siteRoot.length) : dir.replace(/^\//, "");
    const segs = rel.split("/").filter(Boolean);
    return { siteRoot, segs };
}
/** その中間層セグメントを「非リンクの中間表示」にするかどうか */
function isNonLinkableSegment(seg, index, segs) {
    // pages/{画面名}/issues/ は index.md を置かない中間層（規約）→ リンクにしない
    return seg === "issues" && segs[index - 2] === "pages";
}
/** URL パスの各セグメントを辿ってパンくずリンクを組み立てる */
function buildBreadcrumb() {
    const host = document.querySelector("[data-breadcrumb]");
    if (!host)
        return;
    const { siteRoot, segs } = splitPathBySiteRoot();
    const parts = [];
    parts.push(`<a href="${siteRoot}">${BREADCRUMB_LABELS[""]}</a>`);
    // 各セグメントの累積 URL を絶対パス（site root からの絶対）で組む
    let acc = siteRoot;
    segs.forEach((seg, i) => {
        acc += seg + "/";
        const label = BREADCRUMB_LABELS[seg] || seg;
        const isLast = i === segs.length - 1;
        parts.push(`<span class="sep">/</span>`);
        if (isLast || isNonLinkableSegment(seg, i, segs)) {
            // 現在地 or 中間層 → リンクにしない
            parts.push(`<span class="current">${label}</span>`);
        }
        else {
            parts.push(`<a href="${acc}">${label}</a>`);
        }
    });
    host.innerHTML = parts.join("");
}
/* 種類ごとに付ける機能の並び（種類を足すときはここに行を足す） */
const TABLE_KINDS = {
    default: ["pin"],
    data: ["pin", "sort", "count", "columns", "colfilter", "copy", "rowlink"],
    plain: [],
};
/* 機能の名前から付ける関数を引く辞書。並びが操作の段の左からの並びになる（機能を足すときはここに行を足す） */
const TABLE_FEATURES = {
    pin: (state) => enableColumnPin(state.table),
    sort: bindTableSort,
    filter: injectTableFilter,
    colfilter: bindColumnFilters,
    count: bindFilterCount,
    columns: bindColumnToggle,
    total: bindTableTotals,
    copy: bindTableCopy,
    rowlink: bindRowLinks,
};
/* 書けるキーと、そのキーを書くと付く機能（機能を足さないキーは null） */
const TABLE_OPTION_KEYS = {
    hide: "columns",
    total: "total",
    colfilter: "colfilter",
    title: null,
};
/* 範囲を折りたたみに入れる語 */
const RANGE_FOLD_WORDS = ["closed", "open"];
/* 集計の小数の桁数の上限 */
const TOTAL_FRACTION_DIGITS = 2;
const totalFormat = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: TOTAL_FRACTION_DIGITS });
/* 集計の計算（計算の名前 → 先頭列に出す名前・数値として読むか・計算） */
const TABLE_CALCULATIONS = {
    sum: { label: "合計", numeric: true, run: (cells) => cells.reduce((sum, cell) => sum + (parseTableNumber(cell) ?? 0), 0) },
    avg: {
        label: "平均",
        numeric: true,
        run: (cells) => (cells.length ? cells.reduce((sum, cell) => sum + (parseTableNumber(cell) ?? 0), 0) / cells.length : null),
    },
    count: { label: "件数", numeric: false, run: (cells) => cells.length },
};
/* 表の機能で利用者の目に触れる文言（`{名前}` は埋める値、`{choices}` は辞書のキーを `・` でつないだもの） */
const TABLE_LABELS = {
    filter: "この表を絞り込む...",
    filterName: "この表を絞り込む",
    countFiltered: "全 {total} 件中 {shown} 件",
    noMatch: "条件に一致する行はありません",
    columns: "列",
    columnsLegend: "表示する列",
    firstColumn: "（固定）",
    reset: "既定に戻す",
    clearAll: "すべて解除",
    colfilterOpen: "{column} の値で絞り込む",
    colfilterClear: "この列の条件を解除",
    colfilterSearch: "値を検索...",
    colfilterSearchName: "{column} の値を検索",
    colfilterNoValue: "一致する値はありません",
    emptyValue: "（空）",
    totals: "集計",
    totalsLegend: "出す集計",
    close: "閉じる",
    chipClear: "{column} の条件を解除",
    chipsName: "列の値の条件",
    scrollRegion: "表: {heading}",
    warnTitle: "表の指定を読めません",
    totalTitle: "集計を出せません",
    unknownKind: "<!-- table: {value} --> の {value} は使えない種類です。{choices} のどれかを書いてください。この表は既定の種類（ピン留めだけ）で表示します。",
    unknownFeature: "{sign}{value} は使えない機能です。{choices} のどれかを書いてください。",
    unknownKey: "{value}= は使えないキーです。{choices} のどれかを書いてください。",
    unknownColumn: "{key}= の {value} はこの表の列にありません。",
    unknownCalc: "total= の {value} は使えない計算です。{choices} のどれかを書いてください。",
    notNumeric: "{column} の列の {row} 行目（{cell}）を数値として読めないため、{calc}を出していません。",
    foldCount: "表（{n} 件）",
    conflictingKinds: "種類が {values} と複数書かれています。最後に書いた {value} で表示します。",
    firstColumnHidden: "hide= の {value} は先頭列のため隠せません。",
    missingRangeEnd: "<!-- /table --> がありません。この指定を、同じ区切りの最後までの表に当てています。",
    conflictingFold: "closed と open が両方書かれています。後に書いた {value} で表示します。",
    copy: "コピー",
    copyLegend: "コピーする形式",
    copied: "{n} 行をコピーしました",
    rowCopied: "行の URL をコピーしました",
    rowAnchor: "この行へのリンクをコピー",
};
/* 表の機能のボタンに出すアイコン（Octicons の 16px。縦向きのピンは Octicons に無いため描く） */
const TABLE_ICONS = {
    pin: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 1.75A.75.75 0 0 1 5.75 1h4.5a.75.75 0 0 1 0 1.5H10v3.69l2.03 2.03a.75.75 0 0 1 .22.53v.75a.75.75 0 0 1-.75.75H8.75v4.5a.75.75 0 0 1-1.5 0v-4.5H4.5a.75.75 0 0 1-.75-.75v-.75a.75.75 0 0 1 .22-.53L6 6.19V2.5h-.25A.75.75 0 0 1 5 1.75Z"/></svg>',
    sortNone: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="m8.177.677 2.896 2.896a.25.25 0 0 1-.177.427H8.75v1.25a.75.75 0 0 1-1.5 0V4H5.104a.25.25 0 0 1-.177-.427L7.823.677a.25.25 0 0 1 .354 0ZM7.25 10.75a.75.75 0 0 1 1.5 0V12h2.146a.25.25 0 0 1 .177.427l-2.896 2.896a.25.25 0 0 1-.354 0l-2.896-2.896A.25.25 0 0 1 5.104 12H7.25v-1.25Z"/></svg>',
    sortAscending: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="m4.427 9.573 3.396-3.396a.25.25 0 0 1 .354 0l3.396 3.396a.25.25 0 0 1-.177.427H4.604a.25.25 0 0 1-.177-.427Z"/></svg>',
    sortDescending: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z"/></svg>',
    filter: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M.75 3h14.5a.75.75 0 0 1 0 1.5H.75a.75.75 0 0 1 0-1.5ZM3 7.75A.75.75 0 0 1 3.75 7h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 3 7.75Zm3 4a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5a.75.75 0 0 1-.75-.75Z"/></svg>',
    columns: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.75 0h2.5C6.216 0 7 .784 7 1.75v12.5A1.75 1.75 0 0 1 5.25 16h-2.5A1.75 1.75 0 0 1 1 14.25V1.75C1 .784 1.784 0 2.75 0Zm8 0h2.5C14.216 0 15 .784 15 1.75v12.5A1.75 1.75 0 0 1 13.25 16h-2.5A1.75 1.75 0 0 1 9 14.25V1.75C9 .784 9.784 0 10.75 0ZM2.5 1.75v12.5c0 .138.112.25.25.25h2.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25h-2.5a.25.25 0 0 0-.25.25Zm8 0v12.5c0 .138.112.25.25.25h2.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25h-2.5a.25.25 0 0 0-.25.25Z"/></svg>',
    totals: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M9 4.75A.75.75 0 0 1 9.75 4h4a.75.75 0 0 1 .53 1.28l-1.89 1.892c.312.076.604.18.867.319.742.391 1.244 1.063 1.244 2.005 0 .653-.231 1.208-.629 1.627-.386.408-.894.653-1.408.777-1.01.243-2.225.063-3.124-.527a.751.751 0 0 1 .822-1.254c.534.35 1.32.474 1.951.322.306-.073.53-.201.67-.349.129-.136.218-.32.218-.596 0-.308-.123-.509-.444-.678-.373-.197-.98-.318-1.806-.318a.75.75 0 0 1-.53-1.28l1.72-1.72H9.75A.75.75 0 0 1 9 4.75Zm-3.587 5.763c-.35-.05-.77.113-.983.572a.75.75 0 1 1-1.36-.632c.508-1.094 1.589-1.565 2.558-1.425 1 .145 1.872.945 1.872 2.222 0 1.433-1.088 2.192-1.79 2.681-.308.216-.571.397-.772.573H7a.75.75 0 0 1 0 1.5H3.75a.75.75 0 0 1-.75-.75c0-.69.3-1.211.67-1.61.348-.372.8-.676 1.15-.92.8-.56 1.18-.904 1.18-1.474 0-.473-.267-.69-.587-.737ZM5.604.089A.75.75 0 0 1 6 .75v4.77h.711a.75.75 0 0 1 0 1.5H3.759a.75.75 0 0 1 0-1.5H4.5V2.15l-.334.223a.75.75 0 0 1-.832-1.248l1.5-1a.75.75 0 0 1 .77-.037Z"/></svg>',
    x: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/></svg>',
    copy: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"/></svg>',
};
/* 表を描き直すたびに表へ送るイベントの名前（中身は TableFilterDetail） */
const TABLE_FILTER_EVENT = "table-filter";
/* 表のメニューの識別子を振る連番 */
let tableMenuSeq = 0;
/* 表から表の状態を引く対応（行を隠す絞り込みの解除が使う） */
const tableStates = new WeakMap();
/* 行の識別子の頭に付ける語 */
const ROW_ID_PREFIX = "row-";
/* ページで使った行の識別子（見出しの識別子とは別に数える） */
const usedRowIds = new Set();
/* 写す形式（形式の名前 → メニューの文言・添える文言・写す文字列の組み立て。並びがメニューの上からの並びになる。形式を足すときはここに行を足す） */
const TABLE_COPY_FORMATS = {
    markdown: { label: "Markdown", note: "文書に貼る", build: buildMarkdownTable },
    tsv: { label: "TSV", note: "表計算に貼る", build: buildTsvTable },
};
/* 写せなかったときの面で利用者の目に触れる文言 */
const COPY_FALLBACK_LABELS = {
    title: "コピーできませんでした",
    note: "下の欄の中身を選んで Ctrl+C（スマホは長押し）でコピーしてください。",
    areaName: "コピーする中身",
};
/* 写せなかったときの面の識別子を振る連番 */
let copyAnchorSeq = 0;
/** 文言の `{名前}` を値で埋める */
function formatLabel(template, values) {
    return Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), template);
}
/** 要素を作る（文字は textContent で入れ、アイコンの SVG だけ html で入れる） */
function tableEl(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
        if (key === "class")
            node.className = value;
        else if (key === "html")
            node.innerHTML = value;
        else if (key === "text")
            node.textContent = value;
        else
            node.setAttribute(key, value);
    });
    node.append(...children);
    return node;
}
/** 本体の行のセルの文字列（行のアンカーの文字を除き、前後の空白を落とす） */
function tableCellText(row, index) {
    const cell = row.cells[index];
    const text = cell?.textContent || "";
    // 行のアンカーはセルの末尾に置くので、その文字数だけ末尾から外す
    const anchorLength = cell?.querySelector(":scope > .row-anchor")?.textContent?.length ?? 0;
    return text.slice(0, text.length - anchorLength).trim();
}
/** 本文の `<!-- {名前}: 引数 -->`（引数が無ければ `<!-- {名前} -->`）〜 `<!-- /{名前} -->` を読み、範囲の要素と引数を返す（表に限らず、範囲をコメントで包む部品が使う） */
function readRangeDirectives(root, name) {
    const startPattern = new RegExp(`^\\s*${name}(?::\\s*(.*?))?\\s*$`);
    const endPattern = new RegExp(`^\\s*/${name}\\s*$`);
    // 見出しの節の入れ物の中も含めて、始まりのコメントを文書順に集める
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT);
    const starts = [];
    while (walker.nextNode()) {
        const comment = walker.currentNode;
        const match = comment.textContent?.match(startPattern);
        if (match)
            starts.push({ comment, text: match[1] ?? "" });
    }
    return starts.map(({ comment, text }) => {
        // 始まりと同じ親の中で、終わりのコメントまでの要素を範囲にする（終わりが無ければ親の最後まで）
        const nodes = [];
        let node = comment.nextSibling;
        while (node && !(node.nodeType === Node.COMMENT_NODE && endPattern.test(node.textContent || ""))) {
            if (node.nodeType === Node.ELEMENT_NODE)
                nodes.push(node);
            node = node.nextSibling;
        }
        return { start: comment, end: node, nodes, args: parseRangeArgs(text) };
    });
}
/** 範囲の引数を種類・足す機能・外す機能・キーと値・折りたたみに分ける */
function parseRangeArgs(text) {
    const args = { kinds: [], add: [], remove: [], keys: [], fold: null, folds: [] };
    text.split(/\s+/).filter(Boolean).forEach((word) => {
        const fold = RANGE_FOLD_WORDS.find((candidate) => candidate === word);
        if (word.startsWith("+"))
            args.add.push(word.slice(1));
        else if (word.startsWith("-"))
            args.remove.push(word.slice(1));
        else if (word.includes("="))
            args.keys.push([word.slice(0, word.indexOf("=")), word.slice(word.indexOf("=") + 1)]);
        else if (fold) {
            args.folds.push(fold);
            args.fold = fold;
        }
        else
            args.kinds.push(word);
    });
    return args;
}
/** 列見出しの文字（ボタンの文字・アイコンを除く）を返す */
function tableHeaderName(th) {
    const label = th.querySelector(".th-label");
    if (label)
        return (label.textContent || "").trim();
    // 見出しの文字を包む前は、ボタンを除いた見出しの文字を返す
    const clone = th.cloneNode(true);
    clone.querySelectorAll("button").forEach((button) => button.remove());
    return (clone.textContent || "").trim();
}
/** 範囲の引数から、表に付ける機能・機能の引数・警告を決める（知らない指定はその指定だけを当てずに警告へ回す） */
function resolveTableSetup(args, table) {
    const options = { hide: [], total: [], colfilter: null, title: null };
    // 範囲で包まない表は既定の種類
    if (!args)
        return { features: new Set(TABLE_KINDS.default), options, warnings: [] };
    const warnings = [];
    const featureNames = Object.keys(TABLE_FEATURES);
    const kindNames = Object.keys(TABLE_KINDS).filter((kind) => kind !== "default");
    const headers = [...table.tHead.rows[0].cells].map(tableHeaderName);
    // 種類を決める（知らない種類は警告にし、読める種類が複数なら最後に書いた種類）
    const readable = args.kinds.filter((kind) => kindNames.includes(kind));
    args.kinds.filter((kind) => !kindNames.includes(kind)).forEach((value) => {
        warnings.push(formatLabel(TABLE_LABELS.unknownKind, { value, choices: kindNames.join("・") }));
    });
    if (readable.length >= 2) {
        warnings.push(formatLabel(TABLE_LABELS.conflictingKinds, { values: readable.join("・"), value: readable[readable.length - 1] }));
    }
    const kind = (readable[readable.length - 1] ?? "default");
    // 種類の機能に、足す機能・外す機能を当てる
    const features = new Set(TABLE_KINDS[kind]);
    [["+", args.add], ["-", args.remove]].forEach(([sign, names]) => {
        names.forEach((value) => {
            if (!featureNames.includes(value)) {
                warnings.push(formatLabel(TABLE_LABELS.unknownFeature, { sign, value, choices: featureNames.join("・") }));
                return;
            }
            if (sign === "+")
                features.add(value);
            else
                features.delete(value);
        });
    });
    // キーと値を書いた順に読む
    args.keys.forEach(([key, value]) => {
        if (!Object.hasOwn(TABLE_OPTION_KEYS, key)) {
            warnings.push(formatLabel(TABLE_LABELS.unknownKey, { value: key, choices: Object.keys(TABLE_OPTION_KEYS).join("・") }));
            return;
        }
        if (key === "title") {
            options.title = value;
            return;
        }
        features.add(TABLE_OPTION_KEYS[key]);
        value.split(",").filter(Boolean).forEach((item) => {
            // total は `列名:計算` に分ける
            const split = key === "total" ? item.lastIndexOf(":") : -1;
            const column = split >= 0 ? item.slice(0, split) : item;
            const calc = split >= 0 ? item.slice(split + 1) : "";
            const index = headers.indexOf(column);
            if (index < 0) {
                warnings.push(formatLabel(TABLE_LABELS.unknownColumn, { key, value: column }));
                return;
            }
            if (key === "total") {
                if (!Object.hasOwn(TABLE_CALCULATIONS, calc)) {
                    warnings.push(formatLabel(TABLE_LABELS.unknownCalc, { value: calc, choices: Object.keys(TABLE_CALCULATIONS).join("・") }));
                    return;
                }
                options.total.push({ index, calc: calc });
            }
            else if (key === "hide") {
                if (index === 0)
                    warnings.push(formatLabel(TABLE_LABELS.firstColumnHidden, { value: column }));
                else
                    options.hide.push(index);
            }
            else {
                (options.colfilter ??= []).push(index);
            }
        });
    });
    // 集計の指定が 1 つも残らなければ集計行を付けない
    if (options.total.length === 0)
        features.delete("total");
    return { features, options, warnings };
}
/** 表の上に置く警告のコールアウトを作る（見出しの開閉の指定の警告と同じ形） */
function buildTableWarning(title, messages) {
    const box = tableEl("div", { class: "callout callout-warn table-warning", role: "note" }, [tableEl("div", { class: "callout-title", text: title })]);
    // 文が 1 つなら段落、2 つ以上なら箇条書きで置く
    if (messages.length === 1)
        box.append(tableEl("p", { text: messages[0] }));
    else
        box.append(tableEl("ul", {}, messages.map((message) => tableEl("li", { text: message }))));
    return box;
}
/** 本文の表ごとに種類と機能を決め、機能を付ける（表の横スクロールの後、見出しの開閉と列のメニューの紐付けより前に呼ぶ） */
function enhanceTables(article) {
    const ranges = readRangeDirectives(article, "table");
    // 範囲ごとの、折りたたみの見出しに使う最初の表の `title=` と行数
    const firsts = new Map();
    article.querySelectorAll(".table-frame").forEach((frame) => {
        const table = frame.querySelector(":scope > .table-wrap > table");
        // 見出し行か本体の無い表と、付けたマークがある表は飛ばす
        if (!table?.tHead || !table.tBodies[0] || table.dataset.enhanced === "true")
            return;
        // 外側の枠を中の要素（またはその子孫）に持つ範囲を探す
        const range = ranges.find((candidate) => candidate.nodes.some((node) => node === frame || node.contains(frame)));
        const setup = resolveTableSetup(range?.args ?? null, table);
        const { features, options } = setup;
        const warnings = [...setup.warnings];
        // 範囲の中の最初の表の場合、範囲についての警告を足す
        if (range && !firsts.has(range)) {
            if (!range.end)
                warnings.push(TABLE_LABELS.missingRangeEnd);
            if (new Set(range.args.folds).size > 1)
                warnings.push(formatLabel(TABLE_LABELS.conflictingFold, { value: range.args.fold }));
        }
        const rows = [...table.tBodies[0].rows].filter((row) => !row.classList.contains("row-detail"));
        if (range && !firsts.has(range))
            firsts.set(range, { title: options.title, rowCount: rows.length });
        const state = {
            table,
            frame,
            tools: tableEl("div", { class: "table-tools" }),
            options,
            features,
            rows,
            order: [...rows],
            query: "",
            colFilters: new Map(),
            hidden: new Set(options.hide),
            defaultHidden: new Set(options.hide),
            sort: { index: -1, dir: "none" },
            chosenCalcs: new Set(options.total.map((total) => total.calc)),
            invalidTotals: new Set(),
            parts: { count: null, noMatch: null, chips: null, reset: null, columnsButton: null, columnBoxes: null, colButtons: null, colBoxes: null, totalRows: null },
        };
        tableStates.set(table, state);
        // 警告があれば外側の枠の前に置く
        if (warnings.length)
            frame.before(buildTableWarning(TABLE_LABELS.warnTitle, warnings));
        // 機能の辞書の並びの順に、表の機能に入っている名前の関数を呼ぶ
        Object.keys(TABLE_FEATURES).filter((name) => features.has(name)).forEach((name) => TABLE_FEATURES[name](state));
        // 絞り込みの結果で行が無いことの表示を、外側の枠の後ろに隠して置く
        if (features.has("filter") || features.has("colfilter")) {
            state.parts.noMatch = tableEl("p", { class: "table-no-match", text: TABLE_LABELS.noMatch });
            state.parts.noMatch.hidden = true;
            frame.after(state.parts.noMatch);
        }
        // 操作の段に中身があれば、外側の枠の直前（警告の後ろ）に置く
        if (state.tools.childElementCount)
            frame.before(state.tools);
        applyHiddenColumns(state);
        refreshTable(state);
        // 機能のボタンと列の表示で表の幅が変わるので、動かせることを示すマークを付け直す
        markScrollable(frame);
        table.dataset.enhanced = "true";
    });
    // `closed` / `open` を持つ範囲ごとに、機能を付けた後の並び（警告・操作の段・表・行が無いことの表示）で折りたたみに入れる
    ranges.filter((range) => range.args.fold).forEach((range) => {
        const first = firsts.get(range);
        foldTableRange(range, first?.title || formatLabel(TABLE_LABELS.foldCount, { n: first?.rowCount ?? 0 }));
    });
}
/** 絞り込み語と照らす行の文字列を返す（行のアンカーの文字を除く） */
function rowFilterText(row) {
    return [...row.cells].map((_, index) => tableCellText(row, index)).join(" ");
}
/** 今の条件で行の表示・件数・行が無いことの表示・集計行・チップ・ボタンの状態を描き直す */
function refreshTable(state) {
    const { rows, query, colFilters, parts } = state;
    const word = query.toLowerCase();
    rows.forEach((row) => {
        // 絞り込み語は行の文字列（行の詳細を持つ行は行の詳細の行も含めて）に含むか、列の値の条件は列どうしが「かつ」・同じ列の値どうしが「または」
        const detail = rowDetailOf(row);
        const textHit = !word || `${rowFilterText(row)} ${detail?.textContent || ""}`.toLowerCase().includes(word);
        const colHit = [...colFilters].every(([index, values]) => values.has(tableCellText(row, index)));
        row.classList.toggle("hidden", !(textHit && colHit));
        // 行の詳細の行は親の行と同じにする
        detail?.classList.toggle("hidden", !(textHit && colHit));
    });
    const shown = rows.filter((row) => !row.classList.contains("hidden"));
    const filtering = word !== "" || colFilters.size > 0;
    // 件数は絞り込み中だけ出す
    if (parts.count) {
        parts.count.textContent = filtering
            ? formatLabel(TABLE_LABELS.countFiltered, { total: numberFormat.format(rows.length), shown: numberFormat.format(shown.length) })
            : "";
    }
    // 行が無いことの表示は、絞り込み中で残った行が 0 のときだけ出す
    if (parts.noMatch)
        parts.noMatch.hidden = !(filtering && shown.length === 0);
    if (parts.totalRows)
        renderTableTotals(state, shown);
    if (parts.chips)
        renderFilterChips(state);
    parts.colButtons?.forEach((button, index) => button.setAttribute("aria-pressed", String(colFilters.has(index))));
    // 既定に戻すは、隠している列が既定と違うときだけ出す
    if (parts.reset) {
        parts.reset.hidden = state.hidden.size === state.defaultHidden.size && [...state.hidden].every((index) => state.defaultHidden.has(index));
    }
    state.table.dispatchEvent(new CustomEvent(TABLE_FILTER_EVENT, { detail: { total: rows.length, shown: shown.length, filtering } }));
}
/** 列見出しの文字をボタンにし、押下で 昇順 → 降順 → 解除 を巡る */
function bindTableSort(state) {
    const { table } = state;
    const tbody = table.tBodies[0];
    const headCells = [...table.tHead.rows[0].cells];
    const nextDirection = { none: "ascending", ascending: "descending", descending: "none" };
    const sortIcon = {
        none: TABLE_ICONS.sortNone,
        ascending: TABLE_ICONS.sortAscending,
        descending: TABLE_ICONS.sortDescending,
    };
    const marks = headCells.map((th, index) => {
        // 見出しの文字（ピン留めのボタンを除く）を包み、並べ替えの印と一緒に 1 つのボタンへ入れる（印は読み上げず、向きは th の aria-sort で伝える）
        const label = tableEl("span", { class: "th-label" });
        label.append(...[...th.childNodes].filter((node) => !(node instanceof Element && node.matches(".table-pin"))));
        const mark = tableEl("span", { class: "sort-mark", "aria-hidden": "true", html: sortIcon.none });
        const button = tableEl("button", { type: "button", class: "th-sort" }, [label, mark]);
        th.prepend(button);
        th.setAttribute("aria-sort", "none");
        button.addEventListener("click", () => {
            // 並べ替え中の列は昇順 → 降順 → 解除の次の向き、それ以外は昇順
            const dir = state.sort.index === index ? nextDirection[state.sort.dir] : "ascending";
            state.sort = { index, dir };
            // 全ての見出しを戻し、押した見出しに向きと印を入れる
            headCells.forEach((cell) => cell.setAttribute("aria-sort", "none"));
            marks.forEach((other) => { other.innerHTML = sortIcon.none; });
            th.setAttribute("aria-sort", dir);
            mark.innerHTML = sortIcon[dir];
            // 解除は元の並び、それ以外は元の並びを押した列で並べ替えた並びを、行の詳細の行は親の行の直後へ組のまま入れ直す（集計行は動かさない）
            const sign = dir === "ascending" ? 1 : -1;
            // 行を動かすと親の行の直後の行の詳細を引けなくなるため、動かす前に行ごとの行の詳細を取っておく
            const details = new Map(state.order.map((row) => [row, rowDetailOf(row)]));
            const sorted = dir === "none" ? [...state.order] : [...state.order].sort((a, b) => compareCells(tableCellText(a, index), tableCellText(b, index)) * sign);
            sorted.forEach((row) => {
                tbody.appendChild(row);
                const detail = details.get(row);
                if (detail)
                    tbody.appendChild(detail);
            });
        });
        return mark;
    });
}
/** セルの文字列を数値優先で比べる（昇順の結果。降順は呼び出し側が符号を反転する） */
function compareCells(a, b) {
    const left = parseTableNumber(a);
    const right = parseTableNumber(b);
    // 両方が数値として読めれば数値の差、それ以外は日本語の並び
    if (left !== null && right !== null)
        return left - right;
    return a.localeCompare(b, "ja");
}
/** セルの文字列を数値として読む（桁区切りの `,` を許す。空と数値でないものは null） */
function parseTableNumber(text) {
    const value = text.replaceAll(",", "");
    return value === "" || Number.isNaN(Number(value)) ? null : Number(value);
}
/** 操作の段の左端に絞り込み欄を置き、入力語で絞り直す */
function injectTableFilter(state) {
    const input = tableEl("input", { type: "search", class: "table-filter", placeholder: TABLE_LABELS.filter, "aria-label": TABLE_LABELS.filterName });
    input.addEventListener("input", () => {
        state.query = input.value.trim();
        refreshTable(state);
    });
    state.tools.append(input);
}
/** 列見出しに漏斗のボタンと値の一覧を置き、操作の段にチップの並びを置く */
function bindColumnFilters(state) {
    const { table, parts } = state;
    const chips = tableEl("div", { class: "table-chips", "aria-label": TABLE_LABELS.chipsName });
    chips.hidden = true;
    state.tools.append(chips);
    parts.chips = chips;
    parts.colButtons = new Map();
    parts.colBoxes = new Map();
    const headCells = [...table.tHead.rows[0].cells];
    const allowed = state.options.colfilter ?? headCells.map((_, index) => index);
    allowed.forEach((index) => {
        const th = headCells[index];
        const name = tableHeaderName(th);
        const openLabel = formatLabel(TABLE_LABELS.colfilterOpen, { column: name });
        const button = tableEl("button", { type: "button", class: "table-colfilter", "aria-label": openLabel, title: openLabel, html: TABLE_ICONS.filter });
        // ピン留めのボタンの前（無ければ末尾）に置く
        const pin = th.querySelector(".table-pin");
        if (pin)
            pin.before(button);
        else
            th.append(button);
        parts.colButtons.set(index, button);
        // 値は本体の行のその列のセルの文字列で、出てくる順に並べ、値ごとに行の数を添える
        const counts = new Map();
        state.rows.forEach((row) => {
            const value = tableCellText(row, index);
            counts.set(value, (counts.get(value) || 0) + 1);
        });
        const list = tableEl("div", { class: "column-menu-list" });
        const boxes = [...counts].map(([value, n]) => {
            const box = tableEl("input", { type: "checkbox", "data-value": value });
            // 切り替えたら、選んだ値をその列の条件にして描き直す（0 個ならその列の条件を外す）
            box.addEventListener("change", () => {
                const picked = new Set(boxes.filter((other) => other.checked).map((other) => other.dataset.value));
                if (picked.size)
                    state.colFilters.set(index, picked);
                else
                    state.colFilters.delete(index);
                refreshTable(state);
            });
            list.append(tableEl("label", { "data-value": value }, [
                box,
                tableEl("span", { class: "colfilter-value", text: value || TABLE_LABELS.emptyValue }),
                tableEl("span", { class: "colfilter-count", text: numberFormat.format(n) }),
            ]));
            return box;
        });
        parts.colBoxes.set(index, boxes);
        // 一覧の一番下の検索欄は、打った語を含まない値を隠す（表の行は絞らない）
        const noValue = tableEl("p", { class: "colfilter-no-value", text: TABLE_LABELS.colfilterNoValue });
        noValue.hidden = true;
        const search = tableEl("input", {
            type: "search",
            class: "colfilter-search",
            placeholder: TABLE_LABELS.colfilterSearch,
            "aria-label": formatLabel(TABLE_LABELS.colfilterSearchName, { column: name }),
        });
        search.addEventListener("input", () => {
            const word = search.value.trim().toLowerCase();
            const labels = [...list.querySelectorAll("label")];
            labels.forEach((label) => { label.hidden = word !== "" && !label.dataset.value.toLowerCase().includes(word); });
            noValue.hidden = labels.some((label) => !label.hidden);
        });
        const clear = tableEl("button", { type: "button", class: "ghost colfilter-clear", text: TABLE_LABELS.colfilterClear });
        clear.addEventListener("click", () => {
            state.colFilters.delete(index);
            refreshTable(state);
        });
        // 値の一覧は見出しの文字の見た目を受け継がないよう、操作の段の中に置く
        state.tools.append(buildTableMenu({ button, legend: openLabel, list, extras: [noValue, search], actions: [clear] }));
    });
}
/** 適用中の列の値の条件をチップで並べ、1 つずつの解除と全部の解除を置く */
function renderFilterChips(state) {
    const { table, colFilters, parts } = state;
    const chips = parts.chips;
    // 描き直す前にフォーカスがチップの並びの中か「この列の条件を解除」にあったかを覚える
    const focused = document.activeElement;
    const hadFocus = focused instanceof Element && (chips.contains(focused) || focused.matches(".colfilter-clear") && state.tools.contains(focused));
    chips.replaceChildren();
    chips.hidden = colFilters.size === 0;
    // 値の一覧のチェックボックスを今の条件に合わせる
    parts.colBoxes?.forEach((boxes, index) => boxes.forEach((box) => { box.checked = colFilters.get(index)?.has(box.dataset.value) ?? false; }));
    const headCells = [...table.tHead.rows[0].cells];
    colFilters.forEach((values, index) => {
        const label = formatLabel(TABLE_LABELS.chipClear, { column: tableHeaderName(headCells[index]) });
        const chip = tableEl("button", { type: "button", class: "filter-chip", "aria-label": label, title: label }, [
            tableEl("span", { class: "filter-chip-name", text: `${tableHeaderName(headCells[index])}:` }),
            tableEl("span", { class: "filter-chip-values", text: [...values].join("・") }),
        ]);
        chip.insertAdjacentHTML("beforeend", TABLE_ICONS.x);
        chip.addEventListener("click", () => {
            colFilters.delete(index);
            refreshTable(state);
        });
        chips.append(chip);
    });
    // 条件があれば、後ろにすべて解除を置く
    if (colFilters.size) {
        const all = tableEl("button", { type: "button", class: "ghost filter-chip-clear", text: TABLE_LABELS.clearAll });
        all.addEventListener("click", () => {
            colFilters.clear();
            refreshTable(state);
        });
        chips.append(all);
    }
    // 描き直した後に、残った最初のチップへ、チップが無ければ「列」ボタン（無ければ操作の段の最初のボタン）へフォーカスを移す
    // （メニューの中のボタンは隠れているので、操作の段の直下のボタンだけを探す）
    if (hadFocus) {
        const next = chips.querySelector(".filter-chip")
            ?? parts.columnsButton
            ?? state.tools.querySelector(":scope > .column-toggle")
            ?? state.tools.querySelector(":scope > button:not([hidden])");
        next?.focus();
    }
}
/** 操作の段に絞り込み中の件数を置く（文言は描き直しが入れる） */
function bindFilterCount(state) {
    // 表の上の絞り込み欄も列の値の絞り込みも持たない表は何もしない
    if (!state.features.has("filter") && !state.features.has("colfilter"))
        return;
    state.parts.count = tableEl("p", { class: "table-count", "aria-live": "polite" });
    state.tools.append(state.parts.count);
}
/** 操作の段に「既定に戻す」と「列」ボタン・列の表示のメニューを置く */
function bindColumnToggle(state) {
    const { table, parts } = state;
    const headCells = [...table.tHead.rows[0].cells];
    // 既定に戻す: 隠す列を既定に戻し、チェックボックスを合わせ、「列」ボタンへフォーカスを移す
    const reset = tableEl("button", { type: "button", class: "ghost table-reset", text: TABLE_LABELS.reset });
    reset.hidden = true;
    reset.addEventListener("click", () => {
        state.hidden = new Set(state.defaultHidden);
        parts.columnBoxes.forEach((box, index) => { box.checked = !state.hidden.has(index); });
        applyHiddenColumns(state);
        refreshTable(state);
        parts.columnsButton.focus();
    });
    const button = tableEl("button", { type: "button", class: "ghost column-toggle", html: TABLE_ICONS.columns }, [tableEl("span", { text: TABLE_LABELS.columns })]);
    // 列ごとのチェックボックスは、隠していない列を選んだ状態にする（先頭列は外せない）
    const list = tableEl("div", { class: "column-menu-list" });
    parts.columnBoxes = headCells.map((th, index) => {
        const box = tableEl("input", { type: "checkbox" });
        box.checked = !state.hidden.has(index);
        const label = tableEl("label", {}, [box, tableHeaderName(th)]);
        if (index === 0) {
            box.disabled = true;
            label.append(tableEl("span", { class: "column-fixed", text: TABLE_LABELS.firstColumn }));
        }
        box.addEventListener("change", () => {
            if (box.checked)
                state.hidden.delete(index);
            else
                state.hidden.add(index);
            applyHiddenColumns(state);
            refreshTable(state);
        });
        list.append(label);
        return box;
    });
    parts.reset = reset;
    parts.columnsButton = button;
    state.tools.append(reset, button, buildTableMenu({ button, legend: TABLE_LABELS.columnsLegend, list }));
}
/** 隠している列の見出し・セル・集計行のセルに hidden を付け、それ以外から外す */
function applyHiddenColumns(state) {
    // 列の表示切り替えを持たない表は何もしない（開発ドキュメントサーバーが列の組で隠したセルを出さない）
    if (!state.features.has("columns"))
        return;
    // 行の詳細の行（全ての列にまたがる 1 セル）は対象にしない
    [...state.table.rows].filter((row) => !row.classList.contains("row-detail")).forEach((row) => {
        [...row.cells].forEach((cell, index) => { cell.hidden = state.hidden.has(index); });
    });
    positionLineMarkers();
}
/** `tfoot` に計算ごとの集計行を足し、操作の段に「集計」ボタンとメニューを置く */
function bindTableTotals(state) {
    const { table, parts } = state;
    const headCells = [...table.tHead.rows[0].cells];
    // 数値として読む計算の列に、数値として読めないセルがあれば出せない集計に入れ、最初に読めなかった行の警告を作る
    const warnings = [];
    state.options.total.filter(({ calc }) => TABLE_CALCULATIONS[calc].numeric).forEach(({ index, calc }) => {
        const bad = state.rows.findIndex((row) => tableCellText(row, index) !== "" && parseTableNumber(tableCellText(row, index)) === null);
        if (bad < 0)
            return;
        state.invalidTotals.add(`${index}:${calc}`);
        warnings.push(formatLabel(TABLE_LABELS.notNumeric, {
            column: tableHeaderName(headCells[index]),
            row: bad + 1,
            cell: tableCellText(state.rows[bad], index),
            calc: TABLE_CALCULATIONS[calc].label,
        }));
    });
    // 書いた計算の順に、計算ごとの集計行を足す
    const tfoot = table.tFoot ?? table.createTFoot();
    const calcs = [...new Set(state.options.total.map((total) => total.calc))];
    parts.totalRows = calcs.map((calc) => {
        const row = tableEl("tr", { class: "total-row", "data-calc": calc }, headCells.map(() => tableEl("td")));
        tfoot.append(row);
        return row;
    });
    // 「集計」ボタンと、書いた計算のうち出すものを選ぶメニューを操作の段の末尾に置く（計算は最初は全て選んだ状態）
    const button = tableEl("button", { type: "button", class: "ghost column-toggle totals-toggle", html: TABLE_ICONS.totals }, [tableEl("span", { text: TABLE_LABELS.totals })]);
    const list = tableEl("div", { class: "column-menu-list" });
    calcs.forEach((calc) => {
        const box = tableEl("input", { type: "checkbox" });
        box.checked = true;
        box.addEventListener("change", () => {
            if (box.checked)
                state.chosenCalcs.add(calc);
            else
                state.chosenCalcs.delete(calc);
            refreshTable(state);
        });
        list.append(tableEl("label", {}, [box, TABLE_CALCULATIONS[calc].label]));
    });
    state.tools.append(button, buildTableMenu({ button, legend: TABLE_LABELS.totalsLegend, list }));
    // 読めないセルの警告は外側の枠の前に置く
    if (warnings.length)
        state.frame.before(buildTableWarning(TABLE_LABELS.totalTitle, warnings));
}
/** 表示中の行で集計し直す */
function renderTableTotals(state, shown) {
    state.parts.totalRows.forEach((row) => {
        const calc = row.dataset.calc;
        const definition = TABLE_CALCULATIONS[calc];
        // 読み手が「集計」ボタンで外した計算の行は隠し、行のセルを空にして先頭列に計算の名前を入れる
        row.hidden = !state.chosenCalcs.has(calc);
        [...row.cells].forEach((cell) => { cell.textContent = ""; });
        row.cells[0].textContent = definition.label;
        state.options.total.filter((total) => total.calc === calc).forEach(({ index }) => {
            // 出せない集計はセルを空のままにする
            if (state.invalidTotals.has(`${index}:${calc}`))
                return;
            const result = definition.run(shown.map((shownRow) => tableCellText(shownRow, index)).filter((cell) => cell !== ""));
            const text = result === null ? "" : totalFormat.format(result);
            // 先頭列に計算を指定したときは、計算の名前と結果を並べる
            row.cells[index].textContent = index === 0 ? `${definition.label} ${text}` : text;
            row.cells[index].classList.add("total-value");
        });
    });
}
/** ボタンで開くチェックボックスの一覧のメニューを作る（「列」・「集計」と列見出しの絞り込みボタンが共通で使う。置き場所は呼び出し側が決める） */
function buildTableMenu({ button, legend, list, extras = [], actions = [] }) {
    // 一意の識別子を振り、ボタンに開く先と開閉の状態と位置の基準を付ける
    tableMenuSeq += 1;
    const id = `table-menu-${tableMenuSeq}`;
    button.setAttribute("popovertarget", id);
    button.setAttribute("aria-expanded", "false");
    button.style.setProperty("anchor-name", `--${id}`);
    // 外側の押下と Esc が効かないブラウザでも閉じられるよう、閉じるボタンを置く
    const close = tableEl("button", { type: "button", class: "ghost", popovertarget: id, popovertargetaction: "hide", text: TABLE_LABELS.close });
    const menu = tableEl("div", { id, class: "column-menu table-menu", popover: "" }, [
        tableEl("fieldset", {}, [tableEl("legend", { text: legend }), list, ...extras]),
        tableEl("div", { class: "column-menu-actions" }, [...actions, close]),
    ]);
    menu.style.setProperty("position-anchor", `--${id}`);
    menu.addEventListener("toggle", (event) => button.setAttribute("aria-expanded", String(event.newState === "open")));
    return menu;
}
/** 範囲の中の要素を折りたたみ（`details.table-fold`）に入れる */
function foldTableRange(range, summary) {
    // 機能を付けた後の並びで、始まりのコメントから終わりまでの要素を取り直す
    const nodes = [];
    for (let node = range.start.nextSibling; node && node !== range.end; node = node.nextSibling) {
        if (node.nodeType === Node.ELEMENT_NODE)
            nodes.push(node);
    }
    const details = tableEl("details", { class: "table-fold" }, [tableEl("summary", { text: summary })]);
    details.open = range.args.fold === "open";
    range.start.after(details);
    details.append(...nodes);
    return details;
}
/** 操作の段に「コピー」ボタンとコピーする形式のメニューを置く */
function bindTableCopy(state) {
    const button = tableEl("button", { type: "button", class: "ghost column-toggle table-copy", html: TABLE_ICONS.copy }, [tableEl("span", { text: TABLE_LABELS.copy })]);
    const list = tableEl("div", { class: "column-menu-list copy-format-list" });
    const menu = buildTableMenu({ button, legend: TABLE_LABELS.copyLegend, list });
    Object.entries(TABLE_COPY_FORMATS).forEach(([format, { label, note }]) => {
        const item = tableEl("button", { type: "button", class: "ghost copy-format", "data-format": format }, [
            tableEl("span", { class: "copy-format-label", text: label }),
            tableEl("span", { class: "copy-format-note", text: note }),
        ]);
        item.addEventListener("click", async () => {
            menu.hidePopover();
            const { text, rows } = buildTableCopyText(state, format);
            // 写せたら行数を通知で出し、写せなければ手で写せる面を「コピー」ボタンの下に出す
            if (await writeClipboard(text))
                showToast(formatLabel(TABLE_LABELS.copied, { n: rows }));
            else
                showCopyFallback(button, text);
        });
        list.append(item);
    });
    state.tools.append(button, menu);
    // 絞り込みで残った行が無いあいだは、写すものが無いので「コピー」ボタンを隠す
    state.table.addEventListener(TABLE_FILTER_EVENT, (event) => {
        button.hidden = event.detail.shown === 0;
    });
}
/** セルの表示中の文字を返す（行のアンカー・ボタンを除き、`<br>` はセルの中の改行として読む） */
function copyCellText(cell) {
    const clone = cell.cloneNode(true);
    clone.querySelectorAll(".row-anchor, button").forEach((node) => node.remove());
    clone.querySelectorAll("br").forEach((br) => br.replaceWith("\n"));
    return (clone.textContent || "").trim();
}
/** 表示中の本体の行と列を、形式の文字列に組む（行は並べ替えた順、集計行と行の詳細の行は入れない） */
function buildTableCopyText(state, format) {
    const columns = [...state.table.tHead.rows[0].cells].map((th, index) => ({ th, index })).filter(({ th }) => !th.hidden);
    const rows = [...state.table.tBodies[0].rows].filter((row) => !row.classList.contains("row-detail") && !row.classList.contains("hidden"));
    const text = TABLE_COPY_FORMATS[format].build({
        header: columns.map(({ th }) => tableHeaderName(th)),
        body: rows.map((row) => columns.map(({ index }) => copyCellText(row.cells[index]))),
    });
    return { text, rows: rows.length };
}
/** Markdown の表の文字列を組む（セルの `|` は `\|`、セルの中の改行は `<br>` にして、写した先で表を崩さない） */
function buildMarkdownTable({ header, body }) {
    const escape = (text) => text.replaceAll("|", "\\|").replaceAll("\n", "<br>");
    const line = (cells) => `| ${cells.map(escape).join(" | ")} |`;
    return [line(header), `| ${header.map(() => "---").join(" | ")} |`, ...body.map(line)].join("\n");
}
/** TSV の文字列を組む（セルの中の改行とタブは空白にする） */
function buildTsvTable({ header, body }) {
    const clean = (text) => text.replace(/[\t\n]+/g, " ");
    return [header, ...body].map((cells) => cells.map(clean).join("\t")).join("\n");
}
/** 本体の行に識別子を振り、先頭列のセルの文字の後ろに行のアンカーを置く */
function bindRowLinks(state) {
    state.rows.forEach((row) => {
        const cell = row.cells[0];
        const slug = slugify(copyCellText(cell));
        // 空のセル・記号だけのセルの行にはアンカーを付けない
        if (!slug)
            return;
        let id = `${ROW_ID_PREFIX}${slug}`;
        // 同じページで重なれば、2 つ目から連番を付ける
        for (let n = 2; usedRowIds.has(id); n++)
            id = `${ROW_ID_PREFIX}${slug}-${n}`;
        usedRowIds.add(id);
        row.id = id;
        const anchor = tableEl("a", { class: "row-anchor", href: `#${id}`, "aria-label": TABLE_LABELS.rowAnchor, title: TABLE_LABELS.rowAnchor, text: "#" });
        // 押すと URL の断片がその行になり（リンクの既定の動き）、行の URL を写しへ入れる
        anchor.addEventListener("click", async () => {
            const url = `${window.location.origin}${window.location.pathname}${window.location.search}#${id}`;
            if (await writeClipboard(url))
                showToast(TABLE_LABELS.rowCopied);
            else
                showCopyFallback(anchor, url);
        });
        cell.append(anchor);
    });
}
/** 行が絞り込みで隠れていれば、その表の絞り込み語・絞り込み欄・列の値の条件を全て外して描き直す */
function clearRowFilters(row) {
    const state = tableStates.get(row.closest("table"));
    if (!state || !row.classList.contains("hidden"))
        return;
    state.query = "";
    const input = state.tools.querySelector(".table-filter");
    if (input)
        input.value = "";
    state.colFilters.clear();
    refreshTable(state);
}
/* ============================================================================
 * 3. 見出しアンカーリンク
 * ---------------------------------------------------------------------------- */
/** 日本語見出しからも使えるスラッグを生成する */
function slugify(text) {
    return text
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "-")
        // URL で問題になる記号だけ落とす。日本語文字はそのまま残す（modern browser は decode 済で扱う）
        .replace(/[^\p{L}\p{N}\-_.]/gu, "");
}
/* 識別子を割り当てる見出し */
const ANCHORED_HEADINGS = "h2, h3, h4";
/** 範囲の見出しを文書順に見て、重ならない識別子を決めて返す（見出しは書き換えない） */
function resolveHeadingIds(root) {
    const used = new Set();
    const resolved = [];
    root.querySelectorAll(ANCHORED_HEADINGS).forEach((h) => {
        // kramdown の自動 id は日本語を落とす（例: "section"）ため、本文から生成した slug を優先する
        const id = slugify(h.textContent || "") || h.id;
        if (!id)
            return;
        // 重複回避
        let unique = id;
        let n = 2;
        while (used.has(unique))
            unique = `${id}-${n++}`;
        used.add(unique);
        resolved.push({ heading: h, id: unique });
    });
    return resolved;
}
/** h2〜h4 に id と # リンクを付与する */
function insertHeadingAnchors() {
    const root = document.querySelector(".markdown-body");
    if (!root)
        return;
    resolveHeadingIds(root).forEach(({ heading: h, id: unique }) => {
        h.id = unique;
        const a = document.createElement("a");
        a.className = "heading-anchor";
        a.href = `#${unique}`;
        a.setAttribute("aria-label", "この見出しへのリンクをコピー");
        a.textContent = "#";
        // クリック時に URL をクリップボードへコピー（ページ遷移はそのまま）
        a.addEventListener("click", async () => {
            const url = window.location.origin + window.location.pathname + `#${unique}`;
            if (await writeClipboard(url))
                showToast(`URL をコピー: #${unique}`);
            else
                showCopyFallback(a, url);
        });
        h.appendChild(a);
    });
}
/* ============================================================================
 * 4. コードブロックのコピーボタン
 * ---------------------------------------------------------------------------- */
/** `<pre><code>` の右上にコピーボタンを差し込む */
function addCodeCopyButtons() {
    document.querySelectorAll(".markdown-body pre").forEach((pre) => {
        if (pre.dataset.copyReady === "true")
            return;
        pre.dataset.copyReady = "true";
        // 印を当てたコードは、印と消した行を除いた写す中身を `code` の `data-copy-text` に持つ
        codeActions(pre).appendChild(createCopyButton(() => pre.querySelector("code")?.dataset.copyText ?? pre.querySelector("code")?.innerText ?? pre.innerText));
    });
}
/** 入れ物の右上に置く、ボタンを並べる入れ物を返す（無ければ作る） */
function codeActions(container) {
    const existing = container.querySelector(":scope > .code-actions");
    if (existing)
        return existing;
    const actions = document.createElement("div");
    actions.className = "code-actions";
    container.appendChild(actions);
    // 入れ物を position: relative にして右上に置く
    container.style.position = "relative";
    return actions;
}
/** 押すと中身を写しへ入れるボタンを作る */
function createCopyButton(getText) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-copy";
    btn.textContent = "コピー";
    btn.addEventListener("click", async () => {
        if (await writeClipboard(getText())) {
            btn.textContent = "コピー済";
            window.setTimeout(() => { btn.textContent = "コピー"; }, 1500);
        }
        else {
            btn.textContent = "失敗";
        }
    });
    return btn;
}
/** 文字列を写しへ入れ、入れられたかを返す（安全な接続では navigator.clipboard、使えない配信では選択範囲を使う写し方） */
async function writeClipboard(text) {
    if (window.isSecureContext && navigator.clipboard) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        }
        catch {
            return false;
        }
    }
    return copyWithSelection(text);
}
/** 画面に出さないテキスト欄を選択して写しへ入れ、写せたかを返す */
function copyWithSelection(text) {
    const area = document.createElement("textarea");
    area.value = text;
    // 画面に出さず、スクロール位置も動かさない
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    return copied;
}
/* 写せなかったときの面（ページに 1 つだけ置く）と、面を開いた要素 */
let copyFallbackPanel = null;
let copyFallbackSource = null;
/** 写せなかったときの面を作る（ページに 1 つだけ置く） */
function ensureCopyFallbackPanel() {
    if (copyFallbackPanel)
        return copyFallbackPanel;
    const area = tableEl("textarea", { class: "copy-fallback-area", readonly: "", rows: "6", "aria-label": COPY_FALLBACK_LABELS.areaName });
    const close = tableEl("button", { type: "button", class: "ghost", popovertarget: "copy-fallback", popovertargetaction: "hide", text: TABLE_LABELS.close });
    const panel = tableEl("div", { id: "copy-fallback", class: "column-menu table-menu copy-fallback", popover: "", role: "alertdialog", "aria-labelledby": "copy-fallback-title" }, [
        tableEl("p", { id: "copy-fallback-title", class: "copy-fallback-title", text: COPY_FALLBACK_LABELS.title }),
        tableEl("p", { class: "copy-fallback-note", text: COPY_FALLBACK_LABELS.note }),
        area,
        tableEl("div", { class: "column-menu-actions" }, [close]),
    ]);
    // 閉じたら（外側の押下・Esc・閉じる）、面を開いた要素へフォーカスを戻す
    panel.addEventListener("toggle", (event) => {
        if (event.newState === "closed")
            copyFallbackSource?.focus();
    });
    document.body.append(panel);
    copyFallbackPanel = panel;
    return panel;
}
/** 押した要素の下に、写せなかった中身を選んだ状態で置いた面を出す */
function showCopyFallback(source, text) {
    const panel = ensureCopyFallbackPanel();
    // 位置の基準が無い要素には名前を付ける（表のメニューを開くボタンは自分の名前を使う）
    if (!source.style.getPropertyValue("anchor-name")) {
        copyAnchorSeq += 1;
        source.style.setProperty("anchor-name", `--copy-source-${copyAnchorSeq}`);
    }
    panel.style.setProperty("position-anchor", source.style.getPropertyValue("anchor-name"));
    copyFallbackSource = source;
    const area = panel.querySelector("textarea");
    area.value = text;
    panel.showPopover();
    area.focus();
    area.select();
}
/* ============================================================================
 * 5. コールアウト
 * ---------------------------------------------------------------------------- */
/* 引用の先頭に置くマーカーから、付ける class と見出しを引く辞書 */
const CALLOUT_KINDS = {
    NOTE: { className: "callout-note", label: "ノート" },
    TIP: { className: "callout-tip", label: "ヒント" },
    IMPORTANT: { className: "callout-important", label: "重要" },
    WARNING: { className: "callout-warn", label: "警告" },
    CAUTION: { className: "callout-danger", label: "危険" },
};
const CALLOUT_PATTERN = /^\[!([A-Z]+)\]\s*/;
/** 引用の先頭のマーカーを読み、種別の class と見出しを付ける */
function markCallouts(article) {
    article.querySelectorAll("blockquote").forEach((quote) => {
        const head = quote.querySelector("p");
        if (!head || !head.firstChild || head.firstChild.nodeType !== Node.TEXT_NODE)
            return;
        const matched = head.firstChild.nodeValue.match(CALLOUT_PATTERN);
        if (!matched)
            return;
        const kind = CALLOUT_KINDS[matched[1]];
        if (!kind)
            return;
        // マーカーと直後の改行を落として、種別の見出しへ差し替える
        head.firstChild.nodeValue = head.firstChild.nodeValue.replace(CALLOUT_PATTERN, "");
        if (head.firstChild.nodeValue === "" && head.firstChild.nextSibling?.tagName === "BR") {
            head.firstChild.nextSibling.remove();
            head.firstChild.remove();
        }
        const title = document.createElement("div");
        title.className = "callout-title";
        title.textContent = kind.label;
        quote.classList.add("callout", kind.className);
        quote.prepend(title);
    });
}
/* ============================================================================
 * 6. 表の横スクロール
 * ---------------------------------------------------------------------------- */
const WIDE_TABLE_COLUMNS = 7;
/** 表を、動かない外側の枠とスクロールする内側の入れ物の二重で包み、列数の多い表には最終列の開閉を、どの表にも横スクロールの枠の読み上げ名と見出し行の追従を付ける */
function wrapTables(article) {
    // 行の詳細の中の小さな表と、表の機能付けのマーク（data-enhanced）を持つ表（計画画面の表）は包まず、以降の手順の対象からも外す
    const tables = [...article.querySelectorAll('table:not(.sub-table):not([data-enhanced="true"])')];
    const headings = [...article.querySelectorAll("h1, h2, h3, h4")];
    // 同じ見出しの下に表が並ぶときに番号を添えるため、見出しごとの表の数を数える
    const wrapsUnderHeading = new Map();
    tables.forEach((table) => {
        // 動かない外側の枠とスクロールする内側の入れ物の二重で包む
        const frame = document.createElement("div");
        frame.className = "table-frame";
        const wrap = document.createElement("div");
        wrap.className = "table-wrap";
        table.replaceWith(frame);
        frame.appendChild(wrap);
        wrap.appendChild(table);
        // 見出しの列数が多い表は、狭い幅で最終列を畳むマークを付けて行の押下を割り当てる
        if (table.querySelectorAll("thead th").length >= WIDE_TABLE_COLUMNS) {
            frame.classList.add("is-wide");
            enableLastColumnToggle(table);
        }
        // 内側の入れ物を Tab で入れる領域にし、直前の見出しの文字から読み上げ名を付ける（同じ見出しの下の 2 つ目からは番号を添える）
        const heading = headings.filter((candidate) => candidate.compareDocumentPosition(wrap) & Node.DOCUMENT_POSITION_FOLLOWING).at(-1);
        const headingText = heading ? headingLabel(heading) : "";
        const order = (wrapsUnderHeading.get(headingText) ?? 0) + 1;
        wrapsUnderHeading.set(headingText, order);
        wrap.tabIndex = 0;
        wrap.setAttribute("role", "region");
        wrap.setAttribute("aria-label", formatLabel(TABLE_LABELS.scrollRegion, { heading: order > 1 ? `${headingText}（${order}）` : headingText }));
        markScrollable(frame);
    });
    // 包んだ表の見出し行を縦のスクロールに追従させる
    followTableHeads(tables);
}
/** 見出しの文字を返す（アンカーと開閉の印を除く） */
function headingLabel(heading) {
    const clone = heading.cloneNode(true);
    clone.querySelectorAll(".heading-anchor, svg").forEach((mark) => mark.remove());
    return (clone.textContent || "").trim();
}
/** 内側の入れ物が表からはみ出している場合、外側の枠に動かせることを示すマークを付け、はみ出していなければ外す */
function markScrollable(frame) {
    const wrap = frame.querySelector(":scope > .table-wrap");
    frame.classList.toggle("is-scrollable", wrap.querySelector("table").scrollWidth > wrap.clientWidth);
}
/** 列数の多い表で、行の押下に最終列の開閉を割り当てる */
function enableLastColumnToggle(table) {
    // 行の詳細の行と、行の詳細の中の小さな表の行には割り当てない
    [...table.tBodies[0]?.rows || []].forEach((row) => {
        if (row.classList.contains("row-detail"))
            return;
        row.addEventListener("click", () => row.classList.toggle("is-open"));
    });
}
/** 列見出しごとにピン留めボタンを置き、押した列とその左の列を表の左端に留める */
function enableColumnPin(table) {
    // 見出しの行が無ければ何もしない
    const head = table.tHead?.rows[0];
    if (!head)
        return;
    // 表にピン留めを持つマークを付け、見出しごとにピン留めボタンを見出しのセルの末尾に置く
    table.classList.add("has-pin");
    const buttons = [...head.cells].map((th, index) => {
        const label = tableHeaderName(th);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "table-pin";
        button.innerHTML = TABLE_ICONS.pin;
        button.dataset.label = label;
        button.setAttribute("aria-label", `${label} の列まで固定する`);
        // 押下を見出しの並べ替えへ伝えずに、固定する範囲を入れ直す
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            const pinned = table.dataset.pinIndex === String(index);
            table.dataset.pinIndex = pinned ? "" : String(index);
            refresh();
        });
        th.appendChild(button);
        return button;
    });
    /** 固定中の列のボタンだけを押された状態にし、セルの位置を入れ直す */
    function refresh() {
        buttons.forEach((button, index) => {
            const pinned = table.dataset.pinIndex === String(index);
            button.setAttribute("aria-pressed", String(pinned));
            button.title = pinned ? "列の固定を解除" : "この列より左を固定";
        });
        layoutPinned(table);
    }
    refresh();
    // 見出し行のセルの大きさが変わるたびに、1 回の通知でセルの位置を入れ直す
    const observer = new ResizeObserver(() => layoutPinned(table));
    [...head.cells].forEach((th) => observer.observe(th));
}
/** 固定する範囲の列のセルを、手前の列の幅の合計の位置に留める */
function layoutPinned(table) {
    // 行の詳細の行（全ての列にまたがる 1 セル）は固定の対象にしない
    const rows = [...table.rows].filter((row) => !row.classList.contains("row-detail"));
    // 全てのセルから固定のマークと左端からの位置を外す
    rows.forEach((row) => {
        [...row.cells].forEach((cell) => {
            cell.classList.remove("is-pinned", "is-pin-edge");
            cell.style.left = "";
        });
    });
    // 固定する範囲が無ければ終える
    if (!table.dataset.pinIndex)
        return;
    // 1 列目から固定する列まで、見出しと本体の同じ列のセルを手前の列の幅の合計の位置に留める
    const pinIndex = Number(table.dataset.pinIndex);
    const headCells = table.tHead.rows[0].cells;
    let left = 0;
    for (let index = 0; index <= pinIndex; index += 1) {
        rows.forEach((row) => {
            const cell = row.cells[index];
            // セルの足りない行は飛ばす
            if (!cell)
                return;
            cell.classList.add("is-pinned");
            cell.classList.toggle("is-pin-edge", index === pinIndex);
            cell.style.left = `${left}px`;
        });
        left += headCells[index].getBoundingClientRect().width;
    }
}
/** 縦のスクロールに合わせて、表の見出し行を上タブのすぐ下へ送る */
function followTableHeads(tables) {
    // 見出しの行を持つ表が無ければ何もしない
    const targets = tables.filter((table) => table.tHead);
    if (targets.length === 0)
        return;
    const tabbar = document.querySelector(".tabbar");
    let scheduled = false;
    /** 表ごとの送り量を決め直す */
    function update() {
        scheduled = false;
        // 上タブを持たないページ（モックの実画面）は、画面の上端へ送る
        const tabbarBottom = tabbar?.getBoundingClientRect().bottom ?? 0;
        targets.forEach((table) => {
            const rect = table.getBoundingClientRect();
            const headHeight = table.tHead.getBoundingClientRect().height;
            // 上タブの下端から表の上端までの差を、0 から「表の高さ − 見出し行の高さ」までに収める
            const offset = Math.min(Math.max(tabbarBottom - rect.top, 0), rect.height - headHeight);
            // 送り量を表に入れる（見出し行のセルがその分だけ縦へずれる）
            table.style.setProperty("--head-offset", `${offset}px`);
        });
    }
    // スクロールと幅の変更と表の大きさの変更のたびに、描画 1 回分にまとめて決め直す
    const schedule = () => {
        if (scheduled)
            return;
        scheduled = true;
        window.requestAnimationFrame(update);
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const observer = new ResizeObserver(schedule);
    targets.forEach((table) => observer.observe(table));
}
/* ============================================================================
 * 7. Mermaid 描画・拡大
 * ---------------------------------------------------------------------------- */
const ZOOM_WIDTH = "100%";
/** click 構文のリンク先 .md を Pages の .html に書き換える（Jekyll の relative_links はコードブロック内に効かないため） */
function rewriteMermaidLinks(holder) {
    holder.querySelectorAll("a").forEach((a) => {
        const attr = a.hasAttribute("href") ? "href" : "xlink:href";
        const href = a.getAttribute(attr);
        if (!href)
            return;
        a.setAttribute(attr, href.replace(/\.md(#|$)/, ".html$1"));
    });
}
/** 図の元のコードを描き、図の中のリンクと押下での拡大を効かせる */
async function renderMermaid(article) {
    if (!window.mermaid)
        return;
    const blocks = article.querySelectorAll("pre > code.language-mermaid");
    if (blocks.length === 0)
        return;
    // securityLevel: loose で click 構文をリンクとして描画する（GitHub 上では strict のため飾りになる）
    // suppressErrorRendering を外すと、構文エラーの図が body へ描かれたまま残る
    window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        suppressErrorRendering: true,
        theme: document.documentElement.dataset.theme === "dark" ? "dark" : "default",
    });
    for (const [i, code] of blocks.entries()) {
        const pre = code.parentElement;
        const src = code.textContent;
        // div.mermaid-holder を pre の直前に置き、pre は元のコードの表示として隠しておく（元テキストは data-mermaid-src に退避）
        const holder = document.createElement("div");
        holder.className = "mermaid-holder";
        holder.dataset.mermaidSrc = src;
        holder.textContent = "図を描いています...";
        pre.before(holder);
        pre.hidden = true;
        try {
            const id = `mermaid-${Date.now()}-${i}`;
            const { svg, bindFunctions } = await window.mermaid.render(id, src);
            holder.innerHTML = svg;
            rewriteMermaidLinks(holder);
            // click が URL 形式なら <a> で描かれるが、コールバック形式は bindFunctions を呼ばないとハンドラが結ばれない
            bindFunctions?.(holder);
            holder.addEventListener("click", (event) => openZoom(holder, event));
            bindViewToggle(holder, pre, CODE_VIEW_LABELS.diagram);
        }
        catch (e) {
            holder.className = "mermaid-error";
            holder.innerHTML = `<p>図を描けませんでした: ${e?.message ?? e}</p><pre>${src}</pre>`;
        }
    }
}
/** テーマ切替時に既存の Mermaid ホルダーを再描画する */
async function rerenderMermaid() {
    if (!window.mermaid)
        return;
    const holders = document.querySelectorAll(".mermaid-holder[data-mermaid-src]");
    if (holders.length === 0)
        return;
    window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        suppressErrorRendering: true,
        theme: document.documentElement.dataset.theme === "dark" ? "dark" : "default",
    });
    for (const [i, holder] of holders.entries()) {
        const src = holder.dataset.mermaidSrc;
        // 描き直しで中身ごと置き換わるので、操作ボタン群を退避しておく
        const actions = holder.querySelector(":scope > .code-actions");
        try {
            const id = `mermaid-re-${Date.now()}-${i}`;
            const { svg, bindFunctions } = await window.mermaid.render(id, src);
            holder.innerHTML = svg;
            rewriteMermaidLinks(holder);
            bindFunctions?.(holder);
            if (actions)
                holder.appendChild(actions);
        }
        catch (e) {
            holder.className = "mermaid-error";
            holder.innerHTML = `<p>図を描けませんでした: ${e?.message ?? e}</p><pre>${src}</pre>`;
        }
    }
}
/** 図を画面いっぱいに重ねて出し、閉じる手段を配る */
function openZoom(holder, event) {
    // URL 形式の click は <a>、コールバック形式は .clickable として描かれる。リンクの移動と操作ボタンの押下を優先する
    if (event.target.closest("a, .clickable, .code-actions"))
        return;
    const overlay = document.createElement("div");
    overlay.className = "zoom-overlay";
    // 操作ボタン群は複製せず、図だけを重ねる
    overlay.innerHTML = holder.querySelector("svg")?.outerHTML ?? "";
    const close = document.createElement("button");
    close.className = "overlay-close";
    close.textContent = "✕";
    overlay.appendChild(close);
    const svg = overlay.querySelector("svg");
    if (svg) {
        svg.style.width = ZOOM_WIDTH;
        // mermaid が SVG へ inline で入れる max-width に負けるので、こちらも inline で外す
        svg.style.maxWidth = "none";
    }
    const dismiss = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
    };
    const onKey = (key) => {
        if (key.key === "Escape")
            dismiss();
    };
    close.addEventListener("click", dismiss);
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
}
/* ============================================================================
 * 8. 目次
 * ---------------------------------------------------------------------------- */
/** 本文の見出しから目次の並びを作る */
function renderToc(article) {
    const list = document.createElement("ul");
    article.querySelectorAll("h2, h3").forEach((h) => {
        if (!h.id)
            return;
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = `#${h.id}`;
        // アンカー "#" は本文だけ取り出す
        a.textContent = h.textContent.replace(/#$/, "").trim();
        if (h.tagName === "H3")
            a.className = "toc-h3";
        li.appendChild(a);
        list.appendChild(li);
    });
    return list;
}
const TOC_ACTIVE_RATIO = 0.2;
const TOC_LANDING_TOLERANCE_PX = 2;
/** 目次を置き、スクロール位置に応じて現在地を 1 つだけ示す */
function buildToc() {
    const aside = document.querySelector("[data-toc]");
    const article = document.querySelector(".markdown-body");
    if (!aside || !article)
        return;
    const headings = Array.from(article.querySelectorAll("h2, h3"));
    if (headings.length < 2) {
        // 見出し 1 個以下では目次不要
        return;
    }
    aside.hidden = false;
    const toc = renderToc(article);
    const inline = document.createElement("details");
    inline.className = "toc-inline";
    inline.innerHTML = "<summary>目次</summary>";
    layout.toc = toc;
    layout.tocAside = aside;
    layout.tocInline = inline;
    layout.article = article;
    const links = Array.from(toc.querySelectorAll("a"));
    const linkById = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
    // 飛んできた見出しが、飛んだときの位置に留まっていればその見出しを返す
    const jumpedId = (line) => {
        const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
        if (!target || !headings.includes(target))
            return null;
        const top = target.getBoundingClientRect().top;
        const landing = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
        // 着地の位置のまま（次の見出しが近くて線を越えていても、飛んだ先を示す）
        if (Math.abs(top - landing) <= TOC_LANDING_TOLERANCE_PX)
            return target.id;
        // ページの末尾では着地まで上がれないので、画面に入っていれば飛んだ先を示す
        const atBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1;
        return atBottom && top > line && top < window.innerHeight ? target.id : null;
    };
    const updateActive = () => {
        const line = window.innerHeight * TOC_ACTIVE_RATIO;
        let currentId = null;
        for (const h of headings) {
            if (h.getBoundingClientRect().top > line)
                break;
            currentId = h.id;
        }
        currentId = jumpedId(line) || currentId;
        links.forEach((a) => a.classList.remove("active"));
        if (currentId)
            linkById.get(currentId)?.classList.add("active");
    };
    window.addEventListener("scroll", updateActive, { passive: true });
    window.addEventListener("resize", updateActive);
    window.addEventListener("hashchange", () => window.requestAnimationFrame(updateActive));
    updateActive();
}
/* ============================================================================
 * 9. サイドバー
 * ---------------------------------------------------------------------------- */
const OPEN_STATE_KEY = "docsSidebar";
/** 目次表の隠し要素からサイドバーの要素を組み立てる（表が無ければ null） */
function renderSidebar(source, tab, currentPage) {
    if (!source)
        return null;
    const nav = document.createElement("nav");
    nav.className = "docnav";
    // どのセクションにも属さない行（source 直下の表）を、セクションより前に置く
    const looseTable = source.querySelector(":scope > table");
    if (looseTable) {
        const looseRows = [...looseTable.querySelectorAll("tbody tr")];
        nav.appendChild(buildPageList(looseRows, currentPage, tab));
    }
    source.querySelectorAll("[data-section]").forEach((section) => {
        const name = section.dataset.section;
        const rows = [...section.querySelectorAll("tbody tr")];
        const holdsCurrent = rows.some((row) => pageName(row) === currentPage);
        nav.appendChild(buildSection(tab, name, groupRows(rows), currentPage, holdsCurrent));
    });
    if (!nav.hasChildNodes())
        return null;
    return nav;
}
/** 目次表の行を分類列でまとめる（分類列を持たない表はキーが空文字の 1 グループ） */
function groupRows(rows) {
    const groups = new Map();
    rows.forEach((row) => {
        const cell = row.querySelector('[data-col="分類"]');
        const category = cell ? cell.textContent.trim() : "";
        if (!groups.has(category))
            groups.set(category, []);
        groups.get(category).push(row);
    });
    return groups;
}
/** 目次表の行のページ列からページ名を取り出す */
function pageName(row) {
    return row.querySelector('[data-col="ページ"]').textContent.trim();
}
/** セクション 1 つ分の開閉ブロックを作る */
function buildSection(tab, name, groups, currentPage, holdsCurrent) {
    const key = `${tab}:${name}`;
    const open = resolveOpen(key, holdsCurrent);
    const button = openButton(name, open);
    const body = document.createElement("div");
    body.hidden = !open;
    groups.forEach((rows, category) => {
        if (category) {
            body.appendChild(buildSubsection(tab, key, category, rows, currentPage, holdsCurrent));
            return;
        }
        body.appendChild(buildPageList(rows, currentPage, tab));
    });
    bindToggle(button, body, key);
    const section = document.createElement("div");
    section.className = "docnav-section";
    section.append(button, body);
    return section;
}
/** 分類 1 つ分の開閉ブロックを作る */
function buildSubsection(tab, sectionKey, name, rows, currentPage, holdsCurrent) {
    const key = `${sectionKey}/${name}`;
    const holdsCurrentPage = holdsCurrent && rows.some((row) => pageName(row) === currentPage);
    const open = resolveOpen(key, holdsCurrentPage);
    const button = openButton(name, open);
    const list = buildPageList(rows, currentPage, tab);
    list.hidden = !open;
    bindToggle(button, list, key);
    const wrap = document.createElement("div");
    wrap.className = "docnav-subsection";
    wrap.append(button, list);
    return wrap;
}
/** セクション・分類の見出しになる開閉ボタンを作る */
function openButton(name, open) {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-expanded", String(open));
    const label = document.createElement("span");
    label.textContent = name;
    const caret = document.createElement("span");
    caret.className = "docnav-caret";
    caret.textContent = "▸";
    button.append(label, caret);
    return button;
}
/** ボタンの押下に、中身の開閉と状態の記録を割り当てる */
function bindToggle(button, body, key) {
    button.addEventListener("click", () => {
        const next = button.getAttribute("aria-expanded") !== "true";
        button.setAttribute("aria-expanded", String(next));
        body.hidden = !next;
        localStorage.setItem(`${OPEN_STATE_KEY}:${key}`, String(next));
    });
}
/** セクション・分類を開いた状態で描くかを決める（現在地を含む場合は記録より優先して開く） */
function resolveOpen(key, holdsCurrent) {
    if (holdsCurrent)
        return true;
    return localStorage.getItem(`${OPEN_STATE_KEY}:${key}`) === "true";
}
/** 目次表の行順でページの並びを作る */
function buildPageList(rows, currentPage, tab) {
    const list = document.createElement("ul");
    list.className = "docnav-pages";
    rows.forEach((row) => {
        const name = pageName(row);
        const href = row.querySelector('[data-col="ページ"] a')?.getAttribute("href") || "#";
        const item = document.createElement("li");
        const a = document.createElement("a");
        a.textContent = name;
        if (name === currentPage) {
            a.setAttribute("aria-current", "page");
        }
        else {
            a.href = href;
        }
        // 今のタブのフォルダの外へ移るリンクには、別のページへ移るマークを付ける
        if (isOutsideTab(href, tab))
            a.classList.add("docnav-external");
        item.appendChild(a);
        list.appendChild(item);
    });
    return list;
}
/** リンク先が今のタブのフォルダの外（別のタブ・外部のサイト）かを返す */
function isOutsideTab(href, tab) {
    if (href === "#")
        return false;
    const url = new URL(href, window.location.href);
    // 別のサイト: 外
    if (url.origin !== window.location.origin)
        return true;
    // 同じサイト: パスにタブのフォルダを含まなければ外
    const segments = decodeURIComponent(url.pathname).split("/");
    return !segments.includes(tab);
}
/* ============================================================================
 * 10. ドロワー・幅の切り替え
 * ---------------------------------------------------------------------------- */
/** サイドバーを本文の上へ重ねて出し、背景の押下と戻る操作で閉じられるようにする */
function openDrawer(nav) {
    nav.hidden = false;
    const backdrop = document.createElement("div");
    backdrop.className = "drawer-backdrop";
    document.body.appendChild(backdrop);
    history.pushState({ drawer: true }, "");
    const close = () => {
        nav.hidden = true;
        backdrop.remove();
        window.removeEventListener("popstate", close);
        layout.closeDrawer = null;
    };
    layout.closeDrawer = close;
    backdrop.addEventListener("click", () => {
        close();
        history.back();
    });
    window.addEventListener("popstate", close);
}
/** 幅に応じてサイドバーと目次の配置を切り替える */
function applyWidth() {
    // ドロワーを開いたまま広い幅へ変わった場合、閉じて積んだ履歴を戻す
    if (!mobileQuery.matches && layout.closeDrawer) {
        layout.closeDrawer();
        history.back();
    }
    if (layout.nav)
        layout.nav.hidden = mobileQuery.matches;
    if (!layout.toc)
        return;
    if (tocInlineQuery.matches) {
        layout.tocInline.appendChild(layout.toc);
        layout.article.prepend(layout.tocInline);
        return;
    }
    layout.tocInline.remove();
    layout.tocAside.appendChild(layout.toc);
}
/* ============================================================================
 * 11. ダークモード切替
 * ---------------------------------------------------------------------------- */
const THEME_STORAGE_KEY = "docs-theme";
/** 現在のテーマを html[data-theme] に反映 */
function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    // Mermaid にも反映（再描画）
    if (window.mermaid && typeof window.mermaid.initialize === "function") {
        window.mermaid.initialize({ startOnLoad: false, securityLevel: "loose", theme: theme === "dark" ? "dark" : "default" });
    }
}
/** ボタン + localStorage + OS 設定でテーマを決める */
function bindThemeToggle() {
    const btn = document.querySelector("[data-theme-toggle]");
    // OS 設定 → localStorage の順で初期値
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = stored || (prefersDark ? "dark" : "light");
    applyTheme(initial);
    if (!btn)
        return;
    btn.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        applyTheme(next);
        localStorage.setItem(THEME_STORAGE_KEY, next);
        // 既存の mermaid をテーマ変更後に再描画（グラフを破棄して再生成）
        rerenderMermaid();
    });
}
/* ============================================================================
 * 12. コードブロックの言語ラベル
 * ---------------------------------------------------------------------------- */
/** code か構文ハイライトの外枠の class="language-xxx" から言語名を取り出して pre 左上に付ける */
function addCodeLangLabels() {
    document.querySelectorAll(".markdown-body pre").forEach((pre) => {
        // 言語のクラスは code 自身か、rouge が pre.highlight を包む外枠のどちらかに付いている
        const langHolder = pre.classList.contains("highlight")
            ? pre.closest(".highlighter-rouge")
            : pre.querySelector(":scope > code[class*='language-']");
        if (!langHolder)
            return;
        if (pre.dataset.langReady === "true")
            return;
        pre.dataset.langReady = "true";
        const m = /language-([^\s]+)/.exec(langHolder.className);
        if (!m)
            return;
        const lang = m[1];
        // mermaid はラベル不要（図として表示するので）
        if (lang === "mermaid")
            return;
        const label = document.createElement("span");
        label.className = "code-lang";
        label.textContent = lang;
        pre.style.position = "relative";
        pre.appendChild(label);
    });
}
/* ============================================================================
 * 13. 見出し単位の検索
 * ---------------------------------------------------------------------------- */
const SEARCH_RESULT_MAX = 10;
const RECENT_SEARCH_KEY = "docsRecentSearches";
const RECENT_SEARCH_MAX = 5;
let searchIndexCache = null;
/** search.json を初回だけ fetch する（取りに行っている最中の Promise も控える） */
async function loadSearchIndex() {
    if (searchIndexCache)
        return searchIndexCache;
    const url = document.body?.dataset?.searchIndex;
    if (!url)
        return [];
    searchIndexCache = fetch(url)
        .then((res) => {
        if (!res.ok)
            throw new Error("search index fetch failed");
        return res.json();
    })
        .catch(() => {
        // 次の呼び出しで取りに行き直せるよう、失敗した控えは残さない
        searchIndexCache = null;
        return [];
    });
    return searchIndexCache;
}
/** 検索語で索引を絞り、当てはまりの強い順に上位を返す */
function filterSearch(entries, query) {
    const q = query.trim().toLowerCase();
    if (!q)
        return [];
    return entries
        .map((e) => {
        const inHeading = e.heading.toLowerCase().includes(q);
        const inPage = `${e.title} ${e.path}`.toLowerCase().includes(q);
        const inContent = e.content.toLowerCase().includes(q);
        if (!inHeading && !inPage && !inContent)
            return null;
        // 見出し一致を最上位、次に題名 / パス、最後に本文
        const score = (inHeading ? 0 : 100) + (inPage ? 0 : 50);
        return { entry: e, score };
    })
        .filter((x) => x !== null)
        .sort((a, b) => a.score - b.score)
        .slice(0, SEARCH_RESULT_MAX)
        .map((x) => x.entry);
}
/** 結果を入れ物へ並べる。0 件のときはその旨を出す */
function renderResults(container, entries, keyword) {
    container.innerHTML = "";
    if (entries.length === 0) {
        const empty = document.createElement("p");
        empty.className = "search-empty";
        empty.textContent = `「${keyword}」に当たる見出しはありません`;
        container.appendChild(empty);
        return;
    }
    entries.forEach((e) => {
        const a = document.createElement("a");
        a.className = "search-hit";
        a.setAttribute("role", "option");
        a.href = resultHref(e);
        a.innerHTML = `<span class="search-crumb"><span class="search-crumb-page">${escapeHtml(e.title)}</span> › <span class="search-crumb-heading">${highlightMatch(e.heading, keyword)}</span></span><span class="search-excerpt">${highlightMatch(e.content, keyword)}</span>`;
        container.appendChild(a);
    });
}
/** 項目の URL に、その見出しが本文で持つ id を付けた行き先を作る */
function resultHref(entry) {
    if (entry.headingSeq === 0)
        return entry.url;
    let id = slugify(entry.heading);
    if (entry.headingSeq >= 2)
        id += `-${entry.headingSeq}`;
    return `${entry.url}#${id}`;
}
/** 文字列の中で検索語に当たった箇所を強調した HTML を返す */
function highlightMatch(text, query) {
    const q = query.trim();
    const i = text.toLowerCase().indexOf(q.toLowerCase());
    if (!q || i < 0)
        return escapeHtml(text);
    return `${escapeHtml(text.slice(0, i))}<mark>${escapeHtml(text.slice(i, i + q.length))}</mark>${escapeHtml(text.slice(i + q.length))}`;
}
/** 記録から最近の検索語を読む */
function readRecentSearches() {
    try {
        return JSON.parse(localStorage.getItem(RECENT_SEARCH_KEY) || "[]");
    }
    catch {
        return [];
    }
}
/** 結果を開いたときの検索語を、最近の検索の先頭へ足す */
function pushRecentSearch(query) {
    const q = query.trim();
    if (!q)
        return;
    const next = [q, ...readRecentSearches().filter((r) => r !== q)].slice(0, RECENT_SEARCH_MAX);
    localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(next));
}
/** 検索語が空のときに、最近の検索を押せる形で並べる */
function renderRecentSearches(container, input) {
    const recent = readRecentSearches();
    if (recent.length === 0) {
        container.innerHTML = `<p class="search-empty">検索語を入れると、見出しごとに結果が並びます</p>`;
        return;
    }
    container.innerHTML = `<p class="search-group">最近の検索</p>` +
        recent.map((r) => `<button type="button" class="search-recent" data-recent="${escapeHtml(r)}">${OCTICONS.history}<span>${escapeHtml(r)}</span></button>`).join("");
    container.querySelectorAll("[data-recent]").forEach((b) => {
        b.addEventListener("click", () => {
            input.value = b.dataset.recent;
            input.dispatchEvent(new Event("input"));
            input.focus();
        });
    });
}
/** 入力・キー操作・押下を結果の入れ物へ紐付け、今の検索語で描き直す手段を返す */
function bindResultList(container, input, close) {
    let items = [];
    let selected = -1;
    const select = (i) => {
        selected = i;
        container.querySelectorAll(".search-hit").forEach((el, n) => {
            el.classList.toggle("is-selected", n === i);
            el.setAttribute("aria-selected", String(n === i));
            if (n === i)
                el.scrollIntoView({ block: "nearest" });
        });
    };
    const open = (entry) => {
        pushRecentSearch(input.value);
        close();
        navigateWithin(resultHref(entry));
    };
    const render = async () => {
        const query = input.value;
        if (query.trim() === "") {
            renderRecentSearches(container, input);
            items = [];
            selected = -1;
            return;
        }
        if (!searchIndexCache) {
            container.innerHTML = `<p class="search-loading" role="status">索引を読み込んでいます...</p>`;
        }
        const entries = await loadSearchIndex();
        if (input.value !== query)
            return;
        items = filterSearch(entries, query);
        renderResults(container, items, query);
        container.querySelectorAll(".search-hit").forEach((el, i) => {
            el.addEventListener("mousemove", () => select(i));
            el.addEventListener("click", () => {
                pushRecentSearch(input.value);
                close();
            });
        });
        select(items.length ? 0 : -1);
    };
    input.addEventListener("input", render);
    input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" && items.length) {
            e.preventDefault();
            select((selected + 1) % items.length);
        }
        else if (e.key === "ArrowUp" && items.length) {
            e.preventDefault();
            select((selected - 1 + items.length) % items.length);
        }
        else if (e.key === "Enter" && selected >= 0) {
            e.preventDefault();
            open(items[selected]);
        }
        else if (e.key === "Escape") {
            e.preventDefault();
            close();
        }
    });
    return render;
}
/** 入力欄・結果・キー操作の案内を持つモーダルを組み立て、開く手段を返す */
function buildSearchModal() {
    const modal = document.createElement("div");
    modal.className = "search-modal";
    modal.hidden = true;
    modal.innerHTML = `
    <div class="search-modal-backdrop" data-modal-close></div>
    <div class="search-modal-dialog" role="dialog" aria-label="全ページ検索">
      <div class="search-modal-head">
        <input type="search" placeholder="見出しを検索..." aria-label="全ページ検索">
        <button type="button" class="ghost search-modal-close" data-modal-close>閉じる</button>
      </div>
      <div class="search-modal-results" role="listbox"></div>
      <p class="search-modal-keys"><kbd>↑</kbd><kbd>↓</kbd> 選ぶ　<kbd>Enter</kbd> 開く　<kbd>Esc</kbd> 閉じる</p>
    </div>`;
    document.body.appendChild(modal);
    const input = modal.querySelector("input");
    const close = () => {
        modal.hidden = true;
        document.body.classList.remove("search-modal-open");
    };
    const render = bindResultList(modal.querySelector(".search-modal-results"), input, close);
    modal.querySelectorAll("[data-modal-close]").forEach((el) => el.addEventListener("click", close));
    return {
        open() {
            modal.hidden = false;
            document.body.classList.add("search-modal-open");
            render();
            input.focus();
            input.select();
        },
    };
}
/** ヘッダーの入力欄・検索アイコン・Ctrl+K を、同じモーダルへ繋ぐ */
function bindSearchEntries() {
    const modal = buildSearchModal();
    const headerInput = document.querySelector("[data-search-input]");
    if (headerInput) {
        // 入力欄は押すとモーダルを開くだけの見た目にする
        headerInput.readOnly = true;
        headerInput.addEventListener("focus", () => {
            headerInput.blur();
            modal.open();
        });
    }
    document.querySelector("[data-search-toggle]")?.addEventListener("click", () => modal.open());
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            modal.open();
        }
    });
}
/** 結果に出す文字列の記号を無害な表記へ置き換える */
function escapeHtml(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}
/* ============================================================================
 * 14. 起票
 * ---------------------------------------------------------------------------- */
const ISSUE_DRAFT_KEY = "issue-draft";
const ISSUE_URL_MAX = 6000;
const ISSUE_TRUNCATED_NOTE = "\n\n…（長さの上限を超えたため、引用の末尾を切り詰めました）";
/* 開いている起票サイドバーの入力への参照（閉じても要素ごと残す） */
const issueDraft = { panel: null, title: null, body: null, warn: null, initialBody: "" };
/** 共通レイアウトが持つ付けるラベルを並びのまま配列で返す */
function issueLabels() {
    return (document.body?.dataset?.issueLabels || "").split(",");
}
/** 起票サイドバーを組み立てて閉じた状態で置く */
function buildIssuePanel() {
    const panel = document.createElement("aside");
    panel.className = "issue-panel";
    panel.hidden = true;
    panel.setAttribute("aria-label", "Issue を書く");
    const badges = issueLabels().map((label) => `<span class="badge">${escapeHtml(label)}</span>`).join("");
    panel.innerHTML = `
    <div class="issue-panel-head">
      <h2>Issue を書く</h2>
      <button type="button" class="ghost" data-issue-close aria-label="閉じる">✕</button>
    </div>
    <label class="issue-field">
      <span>題名</span>
      <input type="text" data-issue-title>
    </label>
    <label class="issue-field">
      <span>本文</span>
      <textarea data-issue-body rows="12"></textarea>
    </label>
    <p class="issue-warn" data-issue-warn hidden>本文が長いため、GitHub で開くときに引用の末尾を切り詰めます</p>
    <div class="issue-meta">
      <span>付くラベル</span>
      ${badges}
    </div>
    <p class="issue-hint">GitHub の起票画面が別のタブで開きます。送る前にそこで内容を直せます。</p>
    <div class="issue-actions">
      <button type="button" class="ghost" data-issue-clear>クリア</button>
      <button type="button" class="primary" data-issue-submit>GitHub で開く</button>
    </div>`;
    document.querySelector(".docs-layout")?.appendChild(panel);
    issueDraft.panel = panel;
    issueDraft.title = panel.querySelector("[data-issue-title]");
    issueDraft.body = panel.querySelector("[data-issue-body]");
    issueDraft.warn = panel.querySelector("[data-issue-warn]");
    issueDraft.initialBody = issueBodyTemplate();
    issueDraft.body.value = issueDraft.initialBody;
    // 残した下書きがあれば入力欄へ戻す（ページを移ったときと再読み込みしたとき）
    restoreIssueDraft();
    panel.querySelector("[data-issue-close]").addEventListener("click", closeIssuePanel);
    panel.querySelector("[data-issue-clear]").addEventListener("click", clearIssuePanel);
    panel.querySelector("[data-issue-submit]").addEventListener("click", submitIssue);
    issueDraft.body.addEventListener("input", updateIssueWarn);
    issueDraft.title.addEventListener("input", updateIssueWarn);
    // 題名と本文の入力のたびに下書きを残す
    issueDraft.body.addEventListener("input", saveIssueDraft);
    issueDraft.title.addEventListener("input", saveIssueDraft);
}
/** 題名と本文を同じタブの sessionStorage へ残す */
function saveIssueDraft() {
    try {
        sessionStorage.setItem(ISSUE_DRAFT_KEY, JSON.stringify({ title: issueDraft.title.value, body: issueDraft.body.value }));
    }
    catch {
        // sessionStorage が使えない: 残さずに続ける
    }
}
/** sessionStorage に残した題名と本文を入力欄へ戻す */
function restoreIssueDraft() {
    let draft;
    try {
        draft = JSON.parse(sessionStorage.getItem(ISSUE_DRAFT_KEY) || "null");
    }
    catch {
        // 読めない・JSON として壊れている: 何もしない
        return;
    }
    if (!draft)
        return;
    issueDraft.title.value = draft.title || "";
    issueDraft.body.value = draft.body || issueBodyTemplate();
}
/** 該当箇所と内容の 1 ブロックを組み立てる */
function issueBodyTemplate() {
    // ページのパスに、開いている画面の条件を表すクエリ文字列を続ける（無ければパスだけ）
    const pagePath = `${document.body?.dataset?.pagePath || ""}${location.search}`;
    return ["### 該当箇所", "", `- ページ: \`${pagePath}\``, "", "### 内容", "", "", "", "---", ""].join("\n");
}
/** サイドバーを開く */
function openIssuePanel() {
    const { panel, body, title } = issueDraft;
    // 何も書いていなければ、開いた時点の URL で本文を組み直して差し替える（書きかけは変えない）
    const untouched = body.value.trim() === "" || body.value === issueDraft.initialBody;
    if (untouched) {
        body.value = issueBodyTemplate();
        issueDraft.initialBody = body.value;
    }
    panel.hidden = false;
    document.body.classList.add("issue-open");
    updateIssueWarn();
    title.focus();
}
/** サイドバーを閉じる（入力は残す） */
function closeIssuePanel() {
    issueDraft.panel.hidden = true;
    document.body.classList.remove("issue-open");
}
/** 題名・本文・長さの注意を初期状態へ戻す */
function clearIssuePanel() {
    issueDraft.title.value = "";
    issueDraft.initialBody = issueBodyTemplate();
    issueDraft.body.value = issueDraft.initialBody;
    issueDraft.warn.hidden = true;
    // 残した下書きも消す
    try {
        sessionStorage.removeItem(ISSUE_DRAFT_KEY);
    }
    catch {
        // sessionStorage が使えない: 消すものも無い
    }
}
/** 題名・本文・固定のラベルを問い合わせに載せた起票画面の URL を作る */
function buildIssueUrl(title, body) {
    const repo = document.body?.dataset?.issueRepo || "";
    const params = new URLSearchParams({ title, body, labels: issueLabels().join(",") });
    return `https://github.com/${repo}/issues/new?${params.toString()}`;
}
/** URL の長さが上限を超えるときだけ、本文の末尾を切り詰めた URL を返す */
function fitIssueUrl(title, body) {
    const full = buildIssueUrl(title, body);
    if (full.length <= ISSUE_URL_MAX)
        return full;
    let lo = 0;
    let hi = body.length;
    // 収まる本文の長さを二分探索で求める
    while (lo < hi) {
        const mid = Math.ceil((lo + hi) / 2);
        if (buildIssueUrl(title, body.slice(0, mid) + ISSUE_TRUNCATED_NOTE).length <= ISSUE_URL_MAX)
            lo = mid;
        else
            hi = mid - 1;
    }
    return buildIssueUrl(title, body.slice(0, lo) + ISSUE_TRUNCATED_NOTE);
}
/** 今の入力で組み立てた URL が上限を超えるときだけ注意を出す */
function updateIssueWarn() {
    const url = buildIssueUrl(issueDraft.title.value, issueDraft.body.value);
    issueDraft.warn.hidden = url.length <= ISSUE_URL_MAX;
}
/** 組み立てた URL を別のタブで開き、サイドバーの入力を消す */
function submitIssue() {
    const url = fitIssueUrl(issueDraft.title.value, issueDraft.body.value);
    window.open(url, "_blank", "noopener");
    clearIssuePanel();
}
/** ヘッダーの起票ボタンと起票サイドバーを繋ぐ */
function bindIssueEntries() {
    // ヘッダーの起票ボタンが無いページ（開発ドキュメントサーバーの開発者向け資料画面と Pages）では何もしない（起票はコメントのパネルから行う）
    if (!document.querySelector("[data-issue-open]"))
        return;
    buildIssuePanel();
    document.querySelector("[data-issue-open]").addEventListener("click", openIssuePanel);
}
/* ============================================================================
 * 15. トップに戻るボタン
 * ---------------------------------------------------------------------------- */
/** スクロール量で表示切替し、クリックで先頭へスムーズスクロール */
function bindBackToTop() {
    const btn = document.querySelector("[data-back-to-top]");
    if (!btn)
        return;
    const update = () => {
        btn.classList.toggle("visible", window.scrollY > BACK_TO_TOP_THRESHOLD_PX);
    };
    window.addEventListener("scroll", update, { passive: true });
    update();
    btn.addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}
/* ============================================================================
 * 16. Mock demo 用ハンドラ
 * 対象 DOM が無いページでは何もしない（早期 return）。
 * ---------------------------------------------------------------------------- */
/** 検索ボックスの入力語で顧客一覧の行を絞り込む */
function bindSearchFilter() {
    const input = document.getElementById("search");
    if (!input)
        return;
    input.addEventListener("input", () => {
        const keyword = input.value.trim().toLowerCase();
        document.querySelectorAll("#customer-table tbody tr").forEach((row) => {
            const text = row.textContent.toLowerCase();
            row.classList.toggle("hidden", keyword !== "" && !text.includes(keyword));
        });
    });
}
/** 行クリックで疑似遷移トーストを表示する */
function bindRowClick() {
    document.querySelectorAll("#customer-table tbody tr").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (event.target instanceof HTMLInputElement)
                return;
            const id = row.dataset.id;
            showToast(`顧客 ${id} を選択しました（モック）`);
        });
    });
}
/** 新規追加ボタンでトーストを一時表示する */
function bindNewButton() {
    const button = document.getElementById("new-btn");
    if (!button)
        return;
    button.addEventListener("click", () => {
        showToast("新規追加ダイアログを開きました（モック）");
    });
}
/** 詳細画面の編集モードを切り替える */
function bindEditMode() {
    const editBtn = document.getElementById("edit-btn");
    const cancelBtn = document.getElementById("cancel-btn");
    const saveBtn = document.getElementById("save-btn");
    if (!editBtn || !cancelBtn || !saveBtn)
        return;
    /** 編集可能フィールドの readonly 属性を切り替える */
    function setEditing(editing) {
        document.querySelectorAll(".field-value input, .field-value textarea").forEach((field) => {
            if (editing)
                field.removeAttribute("readonly");
            else
                field.setAttribute("readonly", "readonly");
        });
        editBtn.hidden = editing;
        cancelBtn.hidden = !editing;
        saveBtn.hidden = !editing;
    }
    editBtn.addEventListener("click", () => setEditing(true));
    cancelBtn.addEventListener("click", () => setEditing(false));
    saveBtn.addEventListener("click", () => {
        setEditing(false);
        showToast("変更を保存しました（モック）");
    });
}
/* showToast の表示を消すタイマー（重ねて呼ばれたときに前のタイマーを止める） */
let toastTimer;
/** 画面下部のトーストを一定時間表示する */
function showToast(message) {
    const toast = document.getElementById("toast");
    if (!toast)
        return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
        toast.hidden = true;
    }, TOAST_DISPLAY_MS);
}
/* ============================================================================
 * エントリポイント
 * ---------------------------------------------------------------------------- */
/** Mock demo 画面用にトースト要素が無ければ差し込む（他画面の共通機能でも使うため） */
function ensureToastElement() {
    if (document.getElementById("toast"))
        return;
    const t = document.createElement("div");
    t.className = "toast";
    t.id = "toast";
    t.hidden = true;
    document.body.appendChild(t);
}
/* ============================================================================
 * 17. コード内の Markdown
 * ---------------------------------------------------------------------------- */
/* 中身を描いて見せる言語指定 */
const MARKDOWN_LANGS = ["markdown", "md"];
/* 描いた HTML の無害化の設定。<style> を残すと本文の外までスタイルが効く */
const MARKDOWN_SANITIZE_CONFIG = { FORBID_TAGS: ["style"] };
/* 描いた表示と元のコードの切り替えで、利用者の目に触れる文言 */
const CODE_VIEW_LABELS = {
    badge: "Markdown プレビュー",
    raw: "raw",
    preview: "プレビュー",
    diagram: "図",
};
/** 言語指定が markdown のコードブロックの中身を描き、元のコードとの切り替えを付ける */
function renderMarkdownBlocks(article) {
    // ライブラリを取れなかったときは元のコードのまま出す
    const { marked, DOMPurify } = window;
    if (!marked || !DOMPurify)
        return;
    article.querySelectorAll("pre").forEach((pre) => {
        // 言語のクラスは code 自身か、rouge が pre.highlight を包む外枠のどちらかに付いている
        const code = pre.querySelector(":scope > code");
        const langHolder = pre.classList.contains("highlight") ? pre.closest(".highlighter-rouge") : code;
        const lang = /language-([^\s]+)/.exec(langHolder?.className ?? "")?.[1];
        if (!code || !MARKDOWN_LANGS.includes(lang))
            return;
        const src = code.textContent;
        const preview = document.createElement("div");
        preview.className = "markdown-preview";
        preview.innerHTML = DOMPurify.sanitize(marked.parse(src), MARKDOWN_SANITIZE_CONFIG);
        const badge = document.createElement("span");
        badge.className = "markdown-preview-badge";
        badge.textContent = CODE_VIEW_LABELS.badge;
        preview.prepend(badge);
        codeActions(preview).appendChild(createCopyButton(() => src));
        pre.before(preview);
        pre.hidden = true;
        bindViewToggle(preview, pre, CODE_VIEW_LABELS.preview);
    });
}
/** 描いた表示と元のコードの両方へ、互いに切り替えるボタンを置く */
function bindViewToggle(rendered, raw, backLabel) {
    const toRaw = document.createElement("button");
    toRaw.type = "button";
    toRaw.className = "code-view-toggle";
    toRaw.textContent = CODE_VIEW_LABELS.raw;
    codeActions(rendered).appendChild(toRaw);
    const toRendered = document.createElement("button");
    toRendered.type = "button";
    toRendered.className = "code-view-toggle";
    toRendered.textContent = backLabel;
    codeActions(raw).appendChild(toRendered);
    // 押した側を隠して、もう一方を見せる
    toRaw.addEventListener("click", () => {
        rendered.hidden = true;
        raw.hidden = false;
    });
    toRendered.addEventListener("click", () => {
        raw.hidden = true;
        rendered.hidden = false;
    });
}
/* ============================================================================
 * 18. 図の埋め込み
 * ---------------------------------------------------------------------------- */
/** リンクの断片を除いた場所を作る */
function withoutHash(url) {
    const bare = new URL(url);
    bare.hash = "";
    return bare;
}
/** 段落にリンク 1 本だけを置いた位置へ、リンク先の見出しの下の図を置く */
async function embedDiagrams(article) {
    // 埋め込みのリンクを持つ段落: 中身がリンク 1 本だけで、断片を持ち、同じ配信の別のページを指す
    // （本文の直下と節の入れ物の直下の段落。表・箇条書き・引用の中の段落は含めない）
    const targets = [];
    article.querySelectorAll(":scope > p, :scope .section-body > p").forEach((p) => {
        const link = p.firstElementChild;
        if (p.childElementCount !== 1 || link.tagName !== "A")
            return;
        if (p.textContent.trim() !== link.textContent.trim())
            return;
        const url = new URL(link.href, location.href);
        if (url.hash.length <= 1)
            return;
        if (url.origin !== location.origin || url.pathname === location.pathname)
            return;
        targets.push({ paragraph: p, url });
    });
    if (targets.length === 0)
        return;
    // 同じページを指すリンクで 1 度だけ読むための入れ物
    const cache = new Map();
    await Promise.all(targets.map(async ({ paragraph, url }) => {
        // 断片をパーセントデコードする。デコードできなければ段落を残す
        let fragment;
        try {
            fragment = decodeURIComponent(url.hash.slice(1));
        }
        catch (e) {
            console.warn("埋め込みのリンクの断片をデコードできません", url.href, e);
            return;
        }
        // リンク先のページを読む。読めなければ段落を残す
        const pageUrl = withoutHash(url);
        const doc = await fetchSourcePage(pageUrl, cache);
        if (!doc)
            return;
        // 断片が指す見出しの下の図を取り出す。取り出せなければ段落を残す
        const extracted = extractDiagramSources(doc, fragment);
        if (!extracted)
            return;
        // 図ごとにリンクを直して枠に入れ、段落を枠の並びで置き換える
        const figures = extracted.sources.map((source) => buildEmbedFigure(rebaseDiagramLinks(source, pageUrl), extracted, pageUrl));
        paragraph.replaceWith(...figures);
    }));
}
/** 埋め込み元のページを、今のページと同じ配信から読む */
async function fetchSourcePage(url, cache) {
    // 同じ場所の読み込みが入れ物にあれば、その結果を返す
    const cached = cache.get(url.href);
    if (cached)
        return cached;
    const loading = (async () => {
        try {
            const res = await fetch(url);
            // 応答が成功でない場合は読めなかったものとして扱う
            if (!res.ok)
                return null;
            return new DOMParser().parseFromString(await res.text(), "text/html");
        }
        catch (e) {
            console.warn("埋め込み元のページを読めません", url.href, e);
            return null;
        }
    })();
    cache.set(url.href, loading);
    return loading;
}
/** 断片が指す見出しの下にある図の元のコードを、文書順に集める */
function extractDiagramSources(doc, fragment) {
    // 元のページの本文を探す
    const body = doc.querySelector(".markdown-body");
    if (!body)
        return null;
    // 断片と一致する最初の見出しを探す
    const found = resolveHeadingIds(body).find(({ id }) => id === fragment);
    if (!found)
        return null;
    const { heading, id } = found;
    // 見出しの次の要素から、深さが同じか浅い見出しに当たるまで辿って図の元のコードを集める
    const depth = Number(heading.tagName[1]);
    const sources = [];
    for (let el = heading.nextElementSibling; el; el = el.nextElementSibling) {
        if (/^H[1-6]$/.test(el.tagName) && Number(el.tagName[1]) <= depth)
            break;
        el.querySelectorAll("pre > code.language-mermaid").forEach((code) => sources.push(code.textContent));
    }
    if (sources.length === 0)
        return null;
    // ページの題名は本文の h1、無ければ文書の title
    const pageTitle = body.querySelector("h1")?.textContent.trim() || doc.title;
    return { pageTitle, headingText: heading.textContent.trim(), headingId: id, sources };
}
/** 図の元のコードの中のリンクを、差し込み先のページでも同じ先を指す形へ直す */
function rebaseDiagramLinks(source, fromUrl) {
    return source.replace(/(\bclick\s+\S+\s+(?:href\s+)?")([^"]*)(")/g, (whole, head, link, tail) => {
        // スキーム付きの絶対 URL はそのままにする
        if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(link))
            return whole;
        // 相対リンクは元の場所を基準に解決し、配信のルートからのパスと断片へ置き換える
        let resolved;
        try {
            resolved = new URL(link, fromUrl);
        }
        catch (e) {
            // 解決できないリンクはその行をそのままにして、他のリンクと図の埋め込みは続ける
            console.warn("図の中のリンクを解決できません", link, e);
            return whole;
        }
        return `${head}${resolved.pathname}${resolved.search}${resolved.hash}${tail}`;
    });
}
/** 図の元のコードと埋め込み元の表示を、1 つの枠に組む */
function buildEmbedFigure(source, extracted, pageUrl) {
    // 自ページの図と同じ形にして、Mermaid の描画が同じ描き方で拾えるようにする
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.className = "language-mermaid";
    code.textContent = source;
    pre.appendChild(code);
    // 図の下に、埋め込み元の見出しへのリンクを置く
    const from = new URL(pageUrl);
    from.hash = extracted.headingId;
    const link = document.createElement("a");
    link.href = `${from.pathname}${from.search}${from.hash}`;
    link.textContent = `${extracted.pageTitle} › ${extracted.headingText}`;
    const caption = document.createElement("figcaption");
    caption.className = "embed-caption";
    caption.append("埋め込み元: ", link);
    const figure = document.createElement("figure");
    figure.className = "embed-figure";
    figure.append(pre, caption);
    return figure;
}
/* ============================================================================
 * 19. 開発ドキュメントサーバー: リビジョンと差分
 * リビジョンバー・差分のマーク・変更の量・図の変更のマーク・基準を保つリンク。リビジョンバーや差分のマークを持たないページでは何もしない
 * ---------------------------------------------------------------------------- */
/* 全文を出している間に文書へ付けるマーク */
const DIFF_FULL_CLASS = "diff-full";
/* 図の記法から足した状態のマーク（`:::added` と `classDef added` の行）を外す正規表現 */
const ADDED_STATE_LINE_RE = /:::added\b|^\s*classDef added\b.*(?:\n|$)/gm;
/* 差分のマーク・元の行のマークを移す先の要素 */
const MARK_TARGETS = "tr, li, p, h1, h2, h3, h4, h5, h6, blockquote";
/* 数の書式 */
const numberFormat = new Intl.NumberFormat("ja-JP");
/** リビジョンバーの差分と全文の切り替えとコメントのボタンを紐付ける */
function bindRefBar() {
    const bar = document.querySelector("[data-ref-bar]");
    if (!bar)
        return;
    // 差分と全文の切り替えの 2 つのボタンに見せ方の切り替えを割り当てる
    bar.querySelectorAll(".segmented [data-view]").forEach((button) => {
        button.addEventListener("click", () => setDiffView(button.dataset.view));
    });
    // コメントのボタンは書く枠を出さずにパネルを開き、数と読み上げ名に溜めたコメントの数を入れる
    bar.querySelector("[data-comment-open]")?.addEventListener("click", () => openCommentPanel());
    renderCommentButton(loadComments().length);
}
/** 本文の見せ方を差分か全文にする */
async function setDiffView(mode) {
    // 文書に全文のマークを付け外し、選んだボタンを押された見た目にする
    document.documentElement.classList.toggle(DIFF_FULL_CLASS, mode === "full");
    document.querySelectorAll("[data-ref-bar] .segmented [data-view]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.view === mode));
    });
    // 足した状態のマークを持つ生成した図を、全文ならマークを外した記法、差分ならマークつきの記法で描き直す
    const holders = [...document.querySelectorAll(".mermaid-holder[data-mermaid-src]")];
    let changed = false;
    holders.forEach((holder) => {
        const marked = holder.dataset.addedSrc || holder.dataset.mermaidSrc;
        if (!marked.includes(":::added"))
            return;
        holder.dataset.addedSrc = marked;
        holder.dataset.mermaidSrc = mode === "full" ? marked.replace(ADDED_STATE_LINE_RE, "") : marked;
        changed = true;
    });
    if (changed)
        await rerenderMermaid();
    // 行のマークの位置を合わせ直す
    positionLineMarkers();
}
/** 本文の差分のマークを、含む一番近い行・段落・見出しの `diff-add` / `diff-del` へ付け替える */
function applyDiffMarks(article) {
    article.querySelectorAll("span.diff-mark").forEach((mark) => {
        // data-diff の値で、含む一番近い要素に足した行か消した行のマークを付ける
        const target = mark.parentElement?.closest(MARK_TARGETS);
        if (target && article.contains(target))
            target.classList.add(mark.dataset.diff === "del" ? "diff-del" : "diff-add");
        // マークの span を外す（コメントの引用とコピーにマークが入らないようにする）
        mark.remove();
    });
}
/** ページに埋め込んだ JSON を読む（無い・読めなければ空） */
function embeddedJson(id) {
    try {
        return JSON.parse(document.getElementById(id)?.textContent || "{}") || {};
    }
    catch {
        return {};
    }
}
/** 右の目次と本文の節の見出しに、足した行数と消した行数を出す */
function applySectionChanges(article) {
    const sections = embeddedJson("section-changes");
    // JSON が無い・空なら何もしない
    if (Object.keys(sections).length === 0)
        return;
    article.querySelectorAll("h2, h3").forEach((heading) => {
        const text = heading.textContent.replace(/#$/, "").trim();
        const counts = sections[text];
        if (!counts)
            return;
        // 本文の見出しの右に変更の量を足す
        heading.querySelector(".heading-anchor")?.before(changeLabel(counts[0], counts[1]));
        if (!heading.querySelector(".change-count"))
            heading.appendChild(changeLabel(counts[0], counts[1]));
        // 右の目次のその見出しへのリンクにも同じ変更の量を足す（目次の並びは幅に応じて配置が変わるので、並びそのものから引く）
        if (!heading.id || !layout.toc)
            return;
        layout.toc.querySelectorAll(`a[href="#${CSS.escape(heading.id)}"]`).forEach((a) => {
            a.appendChild(changeLabel(counts[0], counts[1]));
        });
    });
}
/** 変わったページの数のバッジを作る */
function changeBadge(count) {
    const badge = document.createElement("span");
    badge.className = "change-badge";
    badge.textContent = numberFormat.format(count);
    badge.setAttribute("aria-label", `変わったページ ${count} 件`);
    return badge;
}
/** サイドバーのページ・セクション・分類に変更の量を出す */
function applySidebarChanges() {
    // 差分を出していないなら何もしない
    if (!document.body.dataset.diff)
        return;
    const source = document.querySelector("[data-sidebar-source]");
    if (!source || !layout.nav)
        return;
    // 元の行のページ名 → 足した行数・消した行数
    const counts = new Map();
    source.querySelectorAll("tr").forEach((row) => {
        const added = Number(row.dataset.added || 0);
        const removed = Number(row.dataset.removed || 0);
        if (added || removed)
            counts.set(pageName(row), [added, removed]);
    });
    // サイドバーのページごとに、変わっていれば変更の量を足す
    layout.nav.querySelectorAll(".docnav-pages a").forEach((a) => {
        const value = counts.get(a.textContent.trim());
        if (!value)
            return;
        a.classList.add("is-changed");
        a.appendChild(changeLabel(value[0], value[1]));
    });
    // セクションの見出しに data-changed の数、分類の見出しに中の変わったページの数を足す
    const changedBySection = new Map([...source.querySelectorAll("[data-section]")].map((s) => [s.dataset.section, Number(s.dataset.changed || 0)]));
    layout.nav.querySelectorAll(".docnav-section").forEach((section) => {
        const label = section.querySelector(":scope > button > span:first-child");
        const changed = changedBySection.get(label?.textContent.trim()) || 0;
        if (changed > 0)
            label.after(changeBadge(changed));
        section.querySelectorAll(".docnav-subsection").forEach((sub) => {
            const subChanged = sub.querySelectorAll(".docnav-pages a.is-changed").length;
            if (subChanged > 0)
                sub.querySelector(":scope > button > span:first-child").after(changeBadge(subChanged));
        });
    });
}
/** 変わった図の枠と raw のボタンに変更の色を付け、raw の表示を元の記法の行の差分にする */
function markDiagramChanges(article) {
    article.querySelectorAll("div.diff-block").forEach((block) => {
        // 直後の図の入れ物（描いた図と元のコード）を 1 つの枠にまとめて changed を付ける
        const holder = block.nextElementSibling;
        if (!holder?.classList.contains("mermaid-holder"))
            return;
        const pre = holder.nextElementSibling;
        const frame = document.createElement("div");
        frame.className = "diagram changed";
        holder.before(frame);
        frame.append(holder);
        if (pre?.tagName === "PRE")
            frame.append(pre);
        // data-lines の行の差分から、行ごとにマークと背景を付けた表示を作り、raw で出す元のコードの代わりに置く
        let lines = [];
        try {
            lines = JSON.parse(block.dataset.lines || "[]");
        }
        catch {
            return;
        }
        const source = document.createElement("pre");
        source.className = "diff-source";
        source.innerHTML = lines.map(([mark, text]) => {
            const cls = mark === "+" ? "diff-add" : mark === "-" ? "diff-del" : "";
            return `<span class="diff-source-line ${cls}"><span class="diff-source-mark" aria-hidden="true">${mark === " " ? "" : escapeHtml(mark)}</span>${escapeHtml(text)}</span>`;
        }).join("");
        pre?.querySelector(":scope > code")?.before(source);
        // 差分を出している間は、生成した図の下の説明に足した状態の凡例を続ける
        const note = frame.nextElementSibling;
        if ((holder.dataset.mermaidSrc || "").includes(":::added") && note?.tagName === "P" && !note.querySelector(".legend-added")) {
            const legend = document.createElement("span");
            legend.className = "legend-added";
            legend.textContent = "追加した状態";
            note.append(" ", legend);
        }
    });
}
/** `+{足した行数}` `-{消した行数}` の表示の要素を作る */
function changeLabel(added, removed) {
    const label = document.createElement("span");
    label.className = "change-count";
    label.setAttribute("aria-label", `${added} 行足し ${removed} 行消し`);
    label.innerHTML = `<span class="add" aria-hidden="true">+${numberFormat.format(added)}</span> <span class="del" aria-hidden="true">-${numberFormat.format(removed)}</span>`;
    return label;
}
/** 同じ配信の中のリンクを辿るときに、行き先に同じ diff を付ける */
function keepDiffOnLinks() {
    const diff = new URL(window.location.href).searchParams.get("diff");
    // URL に diff が無ければ何もしない
    if (!diff)
        return;
    const siteRoot = document.body.dataset.siteRoot || "/";
    // 文書のリンクの押下を 1 か所で受ける
    document.addEventListener("click", (event) => {
        const link = event.target.closest?.("a[href]");
        if (!link || link.hasAttribute("data-ref"))
            return;
        const url = new URL(link.getAttribute("href"), window.location.href);
        // 同じオリジンで data-site-root の下にあり、diff を持たない行き先にだけ足す
        if (url.origin !== window.location.origin || url.searchParams.has("diff"))
            return;
        const projectRoot = siteRoot.replace(/@[^/]+\/$/, "");
        if (!decodeURIComponent(url.pathname).startsWith(decodeURIComponent(projectRoot)))
            return;
        url.searchParams.set("diff", diff);
        link.href = url.href;
    }, { capture: true });
}
/* ============================================================================
 * 20. 開発ドキュメントサーバー: 設計書の表示
 * Schema の説明のタブ・表の件数・項目の要点パネル。対象の要素を持たないページでは何もしない
 * ---------------------------------------------------------------------------- */
/* 項目の要点パネルと表の件数の文言 */
const ITEM_PANEL_LABELS = {
    open: "設計書を開く",
    close: "閉じる",
    missing: "参照先が見つかりません。コミット {commit} の設計書にこの項目はありません。",
    count: "{total} 件",
};
/* Octicons（16px）の形。絵文字は使わない */
const OCTICONS = {
    x: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/></svg>',
    history: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="m.427 1.927 1.215 1.215a8.002 8.002 0 1 1-1.6 5.685.75.75 0 1 1 1.493-.154 6.5 6.5 0 1 0 1.18-4.458l1.358 1.358A.25.25 0 0 1 3.896 6H.25A.25.25 0 0 1 0 5.75V2.104a.25.25 0 0 1 .427-.177ZM7.75 4a.75.75 0 0 1 .75.75v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z"/></svg>',
    link: '<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true"><path d="m7.775 3.275 1.25-1.25a3.5 3.5 0 1 1 4.95 4.95l-2.5 2.5a3.5 3.5 0 0 1-4.95 0 .751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018 1.998 1.998 0 0 0 2.83 0l2.5-2.5a2.002 2.002 0 0 0-2.83-2.83l-1.25 1.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042Zm-4.69 9.64a1.998 1.998 0 0 0 2.83 0l1.25-1.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042l-1.25 1.25a3.5 3.5 0 1 1-4.95-4.95l2.5-2.5a3.5 3.5 0 0 1 4.95 0 .751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018 1.998 1.998 0 0 0-2.83 0l-2.5 2.5a1.998 1.998 0 0 0 0 2.83Z"/></svg>',
};
/* 右の区画のパネル（項目の要点・コメント）の要素と、項目の要点を開いた元 */
const sidePanels = { item: null, comment: null, itemOpener: null };
/** 右の区画のパネルを、閉じた状態で本文の右の列に置く（あれば返す） */
function sidePanel(key, label) {
    if (sidePanels[key])
        return sidePanels[key];
    const panel = document.createElement("aside");
    panel.className = `side-panel ${key}-panel`;
    panel.hidden = true;
    panel.setAttribute("aria-label", label);
    document.querySelector(".docs-layout")?.appendChild(panel);
    sidePanels[key] = panel;
    return panel;
}
/** Schema の説明の項目 / 使用箇所のタブを切り替える */
function bindSchemaTabs(article) {
    const tabs = [...article.querySelectorAll('.schema-tabs [role="tab"]')];
    // タブの並びが無ければ何もしない
    if (tabs.length === 0)
        return;
    const panels = [...article.querySelectorAll(".schema-panel[data-tab]")];
    const select = (tab, focus) => {
        tabs.forEach((t) => {
            const selected = t === tab;
            t.setAttribute("aria-selected", String(selected));
            t.tabIndex = selected ? 0 : -1;
        });
        // 対応するパネルだけを出して他を隠す
        panels.forEach((panel) => { panel.hidden = panel.dataset.tab !== tab.dataset.tab; });
        if (focus)
            tab.focus();
        positionLineMarkers();
    };
    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => select(tab, true));
        tab.addEventListener("keydown", (event) => {
            if (event.key === "ArrowRight")
                select(tabs[(index + 1) % tabs.length], true);
            if (event.key === "ArrowLeft")
                select(tabs[(index - 1 + tabs.length) % tabs.length], true);
        });
    });
    // 最初は項目のタブを選ぶ
    select(tabs.find((tab) => tab.dataset.tab === "items") || tabs[0], false);
}
/** 列の組のマークの後ろの表の外枠を返す（表の警告と表の上の操作の段があれば飛ばす） */
function metaFrame(meta) {
    let next = meta.nextElementSibling;
    while (next?.matches(".table-warning, .table-tools"))
        next = next.nextElementSibling;
    return next;
}
/** 横断の一覧と使用箇所の表に件数を置き、絞り込みのたびに描き直す（絞り込みで行が無いことの表示は表の機能付けが置く） */
function bindTableCounts(article) {
    article.querySelectorAll("div.table-meta").forEach((meta) => {
        if (!["cross", "users"].includes(meta.dataset.table))
            return;
        const frame = metaFrame(meta);
        const table = (frame?.matches("table") ? frame : frame?.querySelector("table"));
        if (!frame || !table?.tBodies[0])
            return;
        const count = document.createElement("p");
        count.className = "table-count";
        // 表の上の操作の段があれば「表示する列」のボタンの前（無ければ末尾）、無ければ表の前に置く
        const tools = frame.previousElementSibling?.matches(".table-tools") ? frame.previousElementSibling : null;
        const toggle = tools?.querySelector(".column-toggle");
        if (toggle)
            toggle.before(count);
        else if (tools)
            tools.append(count);
        else
            frame.before(count);
        // 最初は件数を入れ、絞り込みのたびに、絞り込み中は当たった行の数も添えて描き直す
        const total = [...table.tBodies[0].rows].filter((row) => !row.classList.contains("row-detail")).length;
        count.textContent = formatLabel(ITEM_PANEL_LABELS.count, { total: numberFormat.format(total) });
        table.addEventListener(TABLE_FILTER_EVENT, (event) => {
            const detail = event.detail;
            count.textContent = detail.filtering
                ? formatLabel(TABLE_LABELS.countFiltered, { total: numberFormat.format(detail.total), shown: numberFormat.format(detail.shown) })
                : formatLabel(ITEM_PANEL_LABELS.count, { total: numberFormat.format(detail.total) });
        });
    });
}
/** ページに埋め込んだ項目の要点を読む */
function itemSummaries() {
    return embeddedJson("item-summaries");
}
/** 参照のリンクと横断の一覧の行の押下で、項目の要点パネルを開く */
function bindItemPanel(article) {
    const summaries = itemSummaries();
    // 要点が無ければ何もしない
    if (Object.keys(summaries).length === 0)
        return;
    // Esc で項目の要点パネルを閉じる
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape")
            closeItemPanel();
    });
    // 参照のリンクの押下で、ページを移らずに data-ref の要点でパネルを開く
    article.querySelectorAll("a.ref-link[data-ref]").forEach((link) => {
        link.setAttribute("aria-expanded", "false");
        link.addEventListener("click", (event) => {
            const summary = summaries[link.dataset.ref];
            if (!summary)
                return;
            event.preventDefault();
            openItemPanel(summary, link, link.href);
        });
    });
    // 横断の一覧の表の行に cross-row を付け、行の要点を割り当てる（要点は行の並びと同じ順に並ぶ）
    const meta = [...article.querySelectorAll("div.table-meta")].find((m) => m.dataset.table === "cross");
    const table = meta ? metaFrame(meta)?.querySelector("table") : null;
    if (!table?.tBodies[0])
        return;
    const ordered = Object.values(summaries);
    [...table.tBodies[0].rows].forEach((row, index) => {
        const summary = ordered[index];
        if (!summary)
            return;
        row.classList.add("cross-row");
        row.tabIndex = 0;
        // 行き先は行の設計書のリンクに、項目のパスを断片として付けたもの
        const docLink = row.querySelector("a[href]:not(.row-anchor)");
        const itemPath = summary.ref.split("#")[1] || "";
        const href = docLink ? `${docLink.href.split("#")[0]}${itemPath ? `#${encodeURIComponent(itemPath)}` : ""}` : "";
        const open = () => {
            // 狭い幅では設計書の該当項目へ移る
            if (mobileQuery.matches) {
                if (href)
                    navigateWithin(href);
                return;
            }
            openItemPanel(summary, row, href);
        };
        row.addEventListener("click", (event) => {
            // 行の中の設計書の名前のリンクは、そのまま設計書を開く
            if (event.target.closest("a"))
                return;
            open();
        });
        row.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.target.closest("a"))
                open();
        });
    });
}
/** 項目の要点パネルを開く（コメントのパネルが開いていれば閉じて入れ替わる） */
function openItemPanel(summary, opener, href) {
    // コメントのパネルを閉じる
    closeCommentPanel();
    closeItemPanel(false);
    const panel = sidePanel("item", "項目の要点");
    // 参照先がそのリビジョンに無ければ、欄の代わりに無いことの表示を出す
    const commit = document.querySelector("[data-ref-bar] .ref-bar-value:last-of-type code")?.textContent || "作業ツリー";
    const body = summary.missing
        ? `<p class="item-panel-missing">${escapeHtml(ITEM_PANEL_LABELS.missing.replace("{commit}", commit))}</p>`
        : `<dl>${(summary.fields || []).map(([name, value]) => `<dt>${escapeHtml(name)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>`;
    panel.innerHTML = `
    <div class="side-panel-head">
      <h2 tabindex="-1">${escapeHtml(summary.title)}</h2>
      <button type="button" class="ghost icon-button" data-item-close aria-label="${ITEM_PANEL_LABELS.close}">${OCTICONS.x}</button>
    </div>
    <p class="item-panel-place">${escapeHtml(summary.place)}</p>
    ${body}
    ${href ? `<div class="item-panel-actions"><a href="${escapeHtml(href)}">${ITEM_PANEL_LABELS.open}</a></div>` : ""}`;
    panel.querySelector("[data-item-close]").addEventListener("click", () => closeItemPanel());
    panel.hidden = false;
    document.body.classList.add("side-open");
    // 開いた元に開いた状態を付ける
    sidePanels.itemOpener = opener;
    if (opener.matches("a"))
        opener.setAttribute("aria-expanded", "true");
    else
        opener.classList.add("is-selected");
    panel.querySelector("h2").focus();
    positionLineMarkers();
}
/** 項目の要点パネルを閉じ、開いた元へフォーカスを戻す */
function closeItemPanel(restoreFocus = true) {
    const panel = sidePanels.item;
    // パネルが開いていなければ何もしない
    if (!panel || panel.hidden)
        return;
    panel.hidden = true;
    if (!sidePanels.comment || sidePanels.comment.hidden)
        document.body.classList.remove("side-open");
    const opener = sidePanels.itemOpener;
    sidePanels.itemOpener = null;
    // 開いた元の開いた状態を外してフォーカスを戻す
    if (opener) {
        if (opener.matches("a"))
            opener.setAttribute("aria-expanded", "false");
        else
            opener.classList.remove("is-selected");
        if (restoreFocus)
            opener.focus();
    }
    positionLineMarkers();
}
/* ============================================================================
 * 21. 開発ドキュメントサーバー: 列の表示
 * 列の組のマークの直後の表に「表示する列」のメニューを置く。マークの無い表には置かない
 * ---------------------------------------------------------------------------- */
/* 列のメニューの文言 */
const COLUMN_MENU_LABELS = {
    button: "表示する列",
    once: "今回のみ適用",
    save: "保存して適用",
    all: "すべての列を表示",
    onceDone: "今回のみ適用しました",
    saved: "列の設定を保存しました",
    rejected: "この表の列の組は保存できません。今回のみ適用で当てられます。",
    failed: "設定のファイルに書けないため保存できませんでした。今回のみ適用で当てられます。",
};
/** 列の組のマークの種別・表・列・隠す列を読む（壊れていれば null） */
function readTableMeta(meta) {
    try {
        return {
            kind: meta.dataset.kind,
            table: meta.dataset.table,
            columns: JSON.parse(meta.dataset.columns || "[]"),
            hidden: JSON.parse(meta.dataset.hidden || "[]"),
        };
    }
    catch {
        return null;
    }
}
/** 列の組のマークを持つ表ごとに、表の上に「表示する列」のボタンとメニューを置く */
function bindColumnMenus(article) {
    article.querySelectorAll("div.table-meta").forEach((metaElement, index) => {
        // マークが読めない・後ろに表が無い場合、そのマークは飛ばす
        const meta = readTableMeta(metaElement);
        const frame = metaFrame(metaElement);
        const table = (frame?.matches("table") ? frame : frame?.querySelector("table"));
        if (!meta || !table || !frame)
            return;
        const menu = buildColumnMenu(table, meta);
        const id = `column-menu-${index}`;
        menu.id = id;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ghost column-toggle";
        button.textContent = COLUMN_MENU_LABELS.button;
        button.setAttribute("popovertarget", id);
        button.style.setProperty("anchor-name", `--${id}`);
        menu.style.setProperty("position-anchor", `--${id}`);
        // 表の上の操作の段（表の機能付けが置く）の末尾に足し、無ければ作って外側の枠の前に置く
        let tools = frame.previousElementSibling?.matches(".table-tools") ? frame.previousElementSibling : null;
        if (!tools) {
            tools = document.createElement("div");
            tools.className = "table-tools";
            frame.before(tools);
        }
        // 操作の段に「コピー」ボタンがあれば、その前（「列」の位置）に置き、無ければ末尾に足す
        const copy = tools.querySelector(":scope > .table-copy");
        if (copy)
            copy.before(button, menu);
        else
            tools.append(button, menu);
    });
}
/** 列ごとのチェックボックスと 3 つのボタンと保存の失敗の表示を持つメニューを作る */
function buildColumnMenu(table, meta) {
    const keys = meta.columns.map((column) => (Array.isArray(column) ? column[0] : column));
    const labels = meta.columns.map((column) => (Array.isArray(column) ? column[1] : column));
    const hidden = new Set(meta.hidden);
    const menu = document.createElement("div");
    menu.className = "column-menu";
    menu.setAttribute("popover", "");
    const canSave = Boolean(document.body.dataset.columnsUrl);
    menu.innerHTML = `
    <fieldset>
      <legend>${COLUMN_MENU_LABELS.button}</legend>
      <div class="column-menu-list">
        ${keys.map((key, i) => `<label><input type="checkbox" data-column="${escapeHtml(key)}"${hidden.has(key) ? "" : " checked"}> ${escapeHtml(labels[i])}</label>`).join("")}
      </div>
    </fieldset>
    <p class="column-menu-error" role="alert" hidden></p>
    <div class="column-menu-actions">
      <button type="button" class="ghost" data-column-all>${COLUMN_MENU_LABELS.all}</button>
      <button type="button" class="ghost" data-column-once>${COLUMN_MENU_LABELS.once}</button>
      ${canSave ? `<button type="button" class="primary" data-column-save>${COLUMN_MENU_LABELS.save}</button>` : ""}
    </div>`;
    const error = menu.querySelector(".column-menu-error");
    const current = () => new Set([...menu.querySelectorAll("input[data-column]")].filter((box) => !box.checked).map((box) => box.dataset.column));
    // チェックボックスを選ぶ・外すと、その場で列を出す・隠す
    menu.querySelectorAll("input[data-column]").forEach((box) => {
        box.addEventListener("change", () => showColumns(table, keys, current()));
    });
    // 今回のみ適用: メニューを閉じて通知を出す
    menu.querySelector("[data-column-once]").addEventListener("click", () => {
        menu.hidePopover();
        showToast(COLUMN_MENU_LABELS.onceDone);
    });
    // 保存して適用: 成功ならメニューを閉じて通知、失敗なら応答で分けた文言を出す
    menu.querySelector("[data-column-save]")?.addEventListener("click", async () => {
        error.hidden = true;
        const result = await saveColumns(meta, [...current()]);
        if (result.ok) {
            menu.hidePopover();
            showToast(COLUMN_MENU_LABELS.saved);
            return;
        }
        error.textContent = result.status === 400 || result.status === 404 ? COLUMN_MENU_LABELS.rejected : COLUMN_MENU_LABELS.failed;
        error.hidden = false;
    });
    // すべての列を表示: 全てのチェックボックスを選び、全ての列を出す（保存しない）
    menu.querySelector("[data-column-all]").addEventListener("click", () => {
        menu.querySelectorAll("input[data-column]").forEach((box) => { box.checked = true; });
        showColumns(table, keys, new Set());
    });
    // メニューを閉じたら保存の失敗の表示を消す
    menu.addEventListener("toggle", (event) => {
        if (event.newState === "closed")
            error.hidden = true;
    });
    return menu;
}
/** 表の見出し行とデータ行のセルのうち、隠す列の位置のものに hidden を付け、それ以外から外す */
function showColumns(table, columns, hidden) {
    // 行の詳細の行（全ての列にまたがる 1 セル）は列の表示の対象にしない
    [...table.rows].filter((row) => !row.classList.contains("row-detail")).forEach((row) => {
        [...row.cells].forEach((cell, index) => {
            cell.hidden = hidden.has(columns[index]);
        });
    });
    // 行のマークの位置を合わせ直す
    positionLineMarkers();
}
/** 種別の表の隠す列を PUT {data-columns-url}{kind} で保存する */
async function saveColumns(meta, hidden) {
    const buttons = [...document.querySelectorAll("[data-column-save]")];
    // 保存を待つ間はボタンを押せない状態にして読み込み中の見た目にする
    buttons.forEach((button) => { button.disabled = true; button.setAttribute("aria-busy", "true"); });
    try {
        const res = await fetch(`${document.body.dataset.columnsUrl}${encodeURIComponent(meta.kind)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tables: { [meta.table]: hidden } }),
        });
        return { ok: res.ok, status: res.status };
    }
    catch {
        // 送れなかったときは応答が無い扱いにする
        return { ok: false, status: null };
    }
    finally {
        buttons.forEach((button) => { button.disabled = false; button.removeAttribute("aria-busy"); });
    }
}
/* ============================================================================
 * 22. 開発ドキュメントサーバー: コメント
 * 選んだ文字列へのコメントを溜め、行のマークか見出しと行き来し、まとめてコピー・起票する。data-source-path もトップバーのコメントのボタンも無いページでは何もしない
 * ---------------------------------------------------------------------------- */
/* 溜めたコメントを持つ sessionStorage のキー（同じタブならページを移っても残る） */
const COMMENTS_KEY = "dev-comments";
/* 引用を短くし始める字数と、短くした引用の先頭と末尾に残す字数 */
const QUOTE_MAX = 30;
const QUOTE_KEEP = 12;
/* 移った先のコメントと行を目立たせる時間 */
const FLASH_MS = 1600;
/* コメントまわりの文言 */
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
    noSelection: "コメントを選択してください",
    lineHidden: "該当する行は表示されていません",
    required: "コメントを入力してください",
    markerMenu: "コメント {count} 件",
    jumpLine: "該当行へ移動",
    jumpHeading: "見出しへ移動",
    jumpPage: "ページの先頭へ移動",
    open: "コメント（{count} 件）",
};
/* パネルの書く枠・修正しているコメント・移る先 */
const commentState = { draft: null, editing: null, focusId: null, sequence: 0 };
/** 溜めたコメントを読む（無い・読めない・壊れているときは空） */
function loadComments() {
    try {
        const comments = JSON.parse(sessionStorage.getItem(COMMENTS_KEY) || "[]");
        return Array.isArray(comments) ? comments : [];
    }
    catch {
        return [];
    }
}
/** コメントのボタン（リビジョンバーか Pages のトップバー）の数と読み上げ名を、溜めた数に合わせて描き直す */
function renderCommentButton(count) {
    const button = document.querySelector("[data-comment-open]");
    if (!button)
        return;
    button.setAttribute("aria-label", COMMENT_LABELS.open.replace("{count}", String(count)));
    const badge = button.querySelector("[data-comment-count]");
    if (badge)
        badge.textContent = numberFormat.format(count);
}
/** 溜めたコメントを書き、コメントのボタンの数を描き直す */
function saveComments(comments) {
    try {
        sessionStorage.setItem(COMMENTS_KEY, JSON.stringify(comments));
    }
    catch {
        // 書けなくても続ける
    }
    renderCommentButton(comments.length);
}
/** 本文の元の行のマークを、含む一番近い行・段落・見出しの data-src-line へ移す */
function applySourceLines(article) {
    article.querySelectorAll("span.src-line").forEach((mark) => {
        const target = mark.parentElement?.closest(MARK_TARGETS);
        const line = Number(mark.dataset.line);
        // 既にあれば小さい方を残す
        if (target && article.contains(target) && !Number.isNaN(line)) {
            const current = Number(target.dataset.srcLine);
            if (!target.dataset.srcLine || line < current)
                target.dataset.srcLine = String(line);
        }
        mark.remove();
    });
}
/** 選択範囲より前にある最後の本文の見出しの要素を返す（無ければ null） */
function headingBefore(node) {
    const article = document.querySelector(".markdown-body");
    let found = null;
    for (const heading of article.querySelectorAll("h2, h3")) {
        // 描いた markdown の中の見出しは本文の見出しではないので候補にしない
        if (heading.closest(".markdown-preview"))
            continue;
        // 見出しが選択範囲より前にあれば候補にする
        if (heading.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)
            found = heading;
    }
    return found;
}
/** 選んだ範囲の場所を返す（開発者向け資料画面は元のファイルと始めと終わりの行、Pages はページのパスと直前の見出し） */
function selectionLocation(range) {
    // 元のファイルを持たない（Pages）場合、ページのパスと直前の見出しを返す
    if (!document.body.dataset.sourcePath) {
        const heading = headingBefore(range.startContainer);
        return {
            file: document.body.dataset.pagePath,
            startLine: null,
            endLine: null,
            heading: heading ? heading.textContent.replace(/#$/, "").trim() : null,
            headingId: heading?.id || null,
        };
    }
    const lineOf = (node) => {
        const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        const line = element?.closest("[data-src-line]")?.dataset.srcLine;
        return line ? Number(line) : null;
    };
    const startLine = lineOf(range.startContainer);
    const endLine = lineOf(range.endContainer) ?? startLine;
    return { file: document.body.dataset.sourcePath, startLine, endLine: endLine ?? startLine, heading: null, headingId: null };
}
/** 選んだ文字列を引用の形にする（書記素で数え、長ければ先頭と末尾だけを残す） */
function shortenQuote(text) {
    const flat = text.replace(/\s+/g, " ").trim();
    const graphemes = [...new Intl.Segmenter("ja", { granularity: "grapheme" }).segment(flat)].map((s) => s.segment);
    if (graphemes.length <= QUOTE_MAX)
        return flat;
    return `${graphemes.slice(0, QUOTE_KEEP).join("")} ... ${graphemes.slice(-QUOTE_KEEP).join("")}`;
}
/** コメントの場所の文言を作る */
function formatLocation(comment) {
    // 行があれば行で、行が無く見出しがあれば見出しで（Pages）、どちらも無ければファイルだけで書く
    if (comment.startLine != null) {
        if (comment.startLine === comment.endLine)
            return `${comment.file} ${comment.startLine} 行`;
        return `${comment.file} ${comment.startLine}〜${comment.endLine} 行`;
    }
    if (comment.heading)
        return `${comment.file} › ${comment.heading}`;
    return comment.file;
}
/** 今のページの URL（パスとクエリ） */
function currentPageUrl() {
    return `${window.location.pathname}${window.location.search}`;
}
/** 本文の文字列を選んだときに、選択の下へ「コメントを追加」を出す */
function bindCommentEntry(article) {
    // ボタンを作り、隠した状態で置く
    const button = document.createElement("button");
    button.type = "button";
    button.className = "primary selection-comment";
    button.textContent = COMMENT_LABELS.add;
    button.hidden = true;
    document.body.appendChild(button);
    let pending = null;
    // 選択の変化のたびに出し分ける
    document.addEventListener("selectionchange", () => {
        const selection = document.getSelection();
        const text = selection?.toString().trim();
        // 選択が空、または本文の外なら隠す
        if (!selection || !text || !selection.rangeCount || !article.contains(selection.anchorNode)) {
            button.hidden = true;
            return;
        }
        // 場所と引用を控え、選択の下へボタンを置いて出す
        const range = selection.getRangeAt(0);
        const fragment = range.cloneContents();
        fragment.querySelectorAll(".change-count, .heading-anchor, .row-anchor, .diff-source-mark, .table-pin").forEach((el) => el.remove());
        pending = { ...selectionLocation(range), quote: shortenQuote(fragment.textContent) };
        const rect = range.getBoundingClientRect();
        button.style.top = `${window.scrollY + rect.bottom + 8}px`;
        button.style.left = `${window.scrollX + Math.max(8, Math.min(rect.left, window.innerWidth - 160))}px`;
        button.hidden = false;
    });
    // 押し下げたときは、選択が外れないよう既定の動きを止める
    button.addEventListener("mousedown", (event) => event.preventDefault());
    // 出している間の Esc でボタンだけを隠す（選択は残し、次に選択が変わるまで出さない）
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape")
            button.hidden = true;
    });
    // 押下で書く枠を出してパネルを開き、ボタンを隠して選択を外す
    button.addEventListener("click", () => {
        button.hidden = true;
        openCommentPanel({ draft: pending });
        document.getSelection()?.removeAllRanges();
    });
}
/** コメントのパネルを開く（項目の要点パネルと入れ替わる） */
function openCommentPanel({ draft = null, focusId = null } = {}) {
    // 項目の要点パネルを閉じる
    closeItemPanel(false);
    // 書く枠の値を控えてパネルを描き、開いた状態にする
    commentState.draft = draft;
    commentState.focusId = focusId;
    const panel = sidePanel("comment", COMMENT_LABELS.panel);
    renderCommentPanel();
    panel.hidden = false;
    document.body.classList.add("side-open");
    syncHeaderCommentButton(true);
    positionLineMarkers();
    // 書く枠があれば書く枠まで送って入力欄へ、移る先があればそのコメントまで送って目立たせる
    const input = panel.querySelector("[data-comment-body]");
    if (input) {
        input.closest("form").scrollIntoView({ block: "nearest" });
        input.focus({ preventScroll: true });
    }
    else {
        panel.querySelector("h2").focus({ preventScroll: true });
    }
    flashComment(focusId);
}
/** Pages のヘッダーのコメントのボタンの押した状態を、パネルの開閉に合わせる */
function syncHeaderCommentButton(open) {
    document.querySelector(".topbar [data-comment-open]")?.setAttribute("aria-expanded", String(open));
}
/** 移る先のコメントまで送って一時だけ目立たせる */
function flashComment(id) {
    if (!id || !sidePanels.comment)
        return;
    const item = sidePanels.comment.querySelector(`[data-comment-id="${CSS.escape(id)}"]`);
    if (!item)
        return;
    item.scrollIntoView({ block: "nearest" });
    item.classList.add("flash");
    window.setTimeout(() => item.classList.remove("flash"), FLASH_MS);
}
/** コメントのパネルを閉じる（溜めたコメントは残す） */
function closeCommentPanel() {
    const panel = sidePanels.comment;
    if (!panel || panel.hidden)
        return;
    panel.hidden = true;
    commentState.draft = null;
    commentState.editing = null;
    if (!sidePanels.item || sidePanels.item.hidden)
        document.body.classList.remove("side-open");
    syncHeaderCommentButton(false);
    positionLineMarkers();
}
/** コメント 1 つの HTML */
function commentItemHtml(comment) {
    const editing = commentState.editing === comment.id;
    // 移動のボタンの読み上げ名: 行があれば該当行、行が無く見出しがあれば見出し、どちらも無ければページの先頭
    const jumpLabel = comment.startLine != null ? COMMENT_LABELS.jumpLine : comment.heading ? COMMENT_LABELS.jumpHeading : COMMENT_LABELS.jumpPage;
    const body = editing
        ? `<textarea rows="3" data-edit-body aria-label="${COMMENT_LABELS.panel}">${escapeHtml(comment.body)}</textarea>
       <p class="comment-error" hidden>${COMMENT_LABELS.required}</p>
       <div class="comment-actions">
         <button type="button" class="ghost" data-edit-cancel>${COMMENT_LABELS.cancel}</button>
         <button type="button" class="primary" data-edit-save>${COMMENT_LABELS.save}</button>
       </div>`
        : `<p class="comment-body">${escapeHtml(comment.body)}</p>
       <div class="comment-actions">
         <button type="button" class="ghost" data-comment-edit>${COMMENT_LABELS.edit}</button>
         <button type="button" class="ghost" data-comment-delete>${COMMENT_LABELS.delete}</button>
       </div>`;
    return `
    <li class="comment" data-comment-id="${escapeHtml(comment.id)}">
      <div class="comment-head">
        <input type="checkbox" data-comment-check${comment.selected ? " checked" : ""} aria-label="選択">
        <span class="comment-place">${escapeHtml(formatLocation(comment))}</span>
        <button type="button" class="ghost icon-button" data-comment-jump aria-label="${jumpLabel}" title="${jumpLabel}">${OCTICONS.link}</button>
      </div>
      <blockquote class="comment-quote">${escapeHtml(comment.quote)}</blockquote>
      ${body}
    </li>`;
}
/** 溜めたコメントからパネルの中身を描き直す */
function renderCommentPanel() {
    const panel = sidePanels.comment;
    if (!panel)
        return;
    const comments = loadComments();
    const draft = commentState.draft;
    const selected = comments.filter((c) => c.selected).length;
    // 見出しと閉じるボタン、コメントがあれば一覧の上にすべて選択・起票・コピー
    const toolbar = comments.length === 0 ? "" : `
    <div class="comment-toolbar">
      <label class="comment-all"><input type="checkbox" data-comment-all> ${COMMENT_LABELS.selectAll.replace("{selected}", String(selected)).replace("{total}", String(comments.length))}</label>
      <div class="comment-toolbar-actions">
        <button type="button" class="ghost" data-comment-issue>${COMMENT_LABELS.issue}</button>
        <button type="button" class="primary" data-comment-copy>${COMMENT_LABELS.copy}</button>
      </div>
    </div>`;
    const list = comments.length === 0 ? "" : `<ul class="comment-list">${comments.map(commentItemHtml).join("")}</ul>`;
    // 書く枠の値があれば、最後のコメントのすぐ下（無ければ一番上）に置く
    const form = !draft ? "" : `
    <form class="comment-compose" data-comment-form novalidate>
      <p class="comment-place">${escapeHtml(formatLocation(draft))}</p>
      <blockquote class="comment-quote">${escapeHtml(draft.quote)}</blockquote>
      <textarea rows="3" data-comment-body aria-label="${COMMENT_LABELS.panel}"></textarea>
      <p class="comment-error" hidden>${COMMENT_LABELS.required}</p>
      <div class="comment-actions">
        <button type="button" class="ghost" data-comment-cancel>${COMMENT_LABELS.cancel}</button>
        <button type="submit" class="primary">${COMMENT_LABELS.submit}</button>
      </div>
    </form>`;
    // コメントも書く枠も無ければ、無いことを出す
    const empty = comments.length === 0 && !draft ? `<p class="comment-empty">${COMMENT_LABELS.empty}</p>` : "";
    const scrollTop = panel.scrollTop;
    panel.innerHTML = `
    <div class="side-panel-head">
      <h2 tabindex="-1">${COMMENT_LABELS.panel}</h2>
      <button type="button" class="ghost icon-button" data-comment-close aria-label="閉じる">${OCTICONS.x}</button>
    </div>
    ${toolbar}${list}${form}${empty}`;
    panel.scrollTop = scrollTop;
    panel.querySelector("[data-comment-close]").addEventListener("click", closeCommentPanel);
    // すべて選択: 全てなら選んだ状態、一部なら途中の状態、1 つも無ければ外した状態
    const all = panel.querySelector("[data-comment-all]");
    if (all) {
        all.checked = selected === comments.length;
        all.indeterminate = selected > 0 && selected < comments.length;
        all.addEventListener("change", () => {
            saveComments(loadComments().map((c) => ({ ...c, selected: all.checked })));
            renderCommentPanel();
        });
    }
    panel.querySelector("[data-comment-copy]")?.addEventListener("click", (event) => copyComments(event.currentTarget));
    panel.querySelector("[data-comment-issue]")?.addEventListener("click", (event) => openIssueFromComments(event.currentTarget));
    // コメントごとの操作
    panel.querySelectorAll("[data-comment-id]").forEach((item) => {
        const id = item.dataset.commentId;
        item.querySelector("[data-comment-check]").addEventListener("change", (event) => {
            saveComments(loadComments().map((c) => (c.id === id ? { ...c, selected: event.target.checked } : c)));
            renderCommentPanel();
        });
        item.querySelector("[data-comment-jump]").addEventListener("click", () => {
            const comment = loadComments().find((c) => c.id === id);
            if (!comment)
                return;
            if (comment.startLine != null)
                jumpToLine(comment);
            else
                jumpToHeading(comment);
        });
        item.querySelector("[data-comment-edit]")?.addEventListener("click", () => {
            commentState.editing = id;
            renderCommentPanel();
            panel.querySelector("[data-edit-body]")?.focus();
        });
        item.querySelector("[data-comment-delete]")?.addEventListener("click", () => deleteComment(id));
        item.querySelector("[data-edit-cancel]")?.addEventListener("click", () => {
            commentState.editing = null;
            renderCommentPanel();
        });
        item.querySelector("[data-edit-save]")?.addEventListener("click", () => {
            updateComment(id, item.querySelector("[data-edit-body]").value);
        });
    });
    // 書く枠のキャンセルと追加
    panel.querySelector("[data-comment-cancel]")?.addEventListener("click", () => {
        commentState.draft = null;
        renderCommentPanel();
    });
    panel.querySelector("[data-comment-form]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        addComment(draft, panel.querySelector("[data-comment-body]").value);
    });
}
/** 入力チェックのエラーを入力欄の下に出す */
function showCommentError(input) {
    const error = input.parentElement.querySelector(".comment-error");
    if (error)
        error.hidden = false;
    input.setAttribute("aria-invalid", "true");
    input.focus();
}
/** 書く枠の本文を、選んだ状態のコメントとして一覧の末尾へ足す */
function addComment(draft, body) {
    const input = sidePanels.comment?.querySelector("[data-comment-body]");
    // 本文が空白だけなら、入力欄の下にエラーを出す（入力は消さない）
    if (!body.trim()) {
        if (input)
            showCommentError(input);
        return false;
    }
    commentState.sequence += 1;
    const id = `c-${Date.now()}-${commentState.sequence}`;
    const comment = { ...draft, id, body: body.trim(), page: currentPageUrl(), selected: true, copied: false };
    // 末尾へ足して保存し、書く枠を閉じてパネルと行のマークを描き直す
    saveComments([...loadComments(), comment]);
    commentState.draft = null;
    renderCommentPanel();
    renderLineMarkers();
    // 足したコメントまで送って一時だけ目立たせる
    flashComment(id);
    return true;
}
/** コメントの本文を直し、コピー済みを外す */
function updateComment(id, body) {
    const input = sidePanels.comment?.querySelector("[data-edit-body]");
    if (!body.trim()) {
        if (input)
            showCommentError(input);
        return false;
    }
    saveComments(loadComments().map((c) => (c.id === id ? { ...c, body: body.trim(), copied: false } : c)));
    commentState.editing = null;
    renderCommentPanel();
    return true;
}
/** コメントを一覧から消す */
function deleteComment(id) {
    saveComments(loadComments().filter((c) => c.id !== id));
    renderCommentPanel();
    renderLineMarkers();
}
/** 選んだコメントを一覧の順にクリップボードへ書く形にまとめる */
function buildClipboardText(comments) {
    return comments.map((c) => `${formatLocation(c)}\n> ${c.quote}\n\n${c.body}`).join("\n\n---\n\n");
}
/** 選んだコメントをまとめてクリップボードへ書く（写せなかったときは、押したボタンの下に写せなかったときの面を出す） */
async function copyComments(source) {
    const comments = loadComments();
    const selected = comments.filter((c) => c.selected);
    // 選んだコメントが無ければ通知を出して終わる
    if (selected.length === 0) {
        showToast(COMMENT_LABELS.noSelection);
        return false;
    }
    // 写せなければ、まとめた文字列を入れた写せなかったときの面を出して終わる（通知は出さない）
    const text = buildClipboardText(selected);
    if (!(await writeClipboard(text))) {
        showCopyFallback(source, text);
        return false;
    }
    // 選んだコメントの copied を付けて保存し、通知を出す
    saveComments(comments.map((c) => (c.selected ? { ...c, copied: true } : c)));
    showToast(COMMENT_LABELS.copied);
    return true;
}
/** 選んだコメントをコピーしてから、GitHub の Issue の起票画面を別のタブで開く */
async function openIssueFromComments(source) {
    // 書けなかった場合（選んだコメントが無い・写せなかったときの面を出した）、開かずに終わる
    if (!(await copyComments(source)))
        return;
    const repo = document.body.dataset.issueRepo || "";
    const params = new URLSearchParams({ labels: issueLabels().join(",") });
    window.open(`https://github.com/${repo}/issues/new?${params.toString()}`, "_blank", "noopener");
}
/** data-src-line が行の要素を、隠れているものも含めて全て引く */
function sourceLineElements(line) {
    return [...document.querySelectorAll(`.markdown-body [data-src-line="${line}"]`)];
}
/** data-src-line が行の要素を引く（消した行と足した行が同じ番号なら、今出ている方） */
function lineElement(line) {
    return sourceLineElements(line).find((el) => el.getClientRects().length > 0) ?? null;
}
/** コメントを付けた行へ移り、行を一時だけ目立たせる */
function jumpToLine(comment) {
    // コメントのページが今のページでなければ、そのページを #L{始めの行} 付きで開いて終わる
    const target = new URL(comment.page, window.location.href);
    if (`${target.pathname}${target.search}` !== currentPageUrl()) {
        target.hash = comment.startLine != null ? `L${comment.startLine}` : "";
        navigateWithin(target.href);
        return;
    }
    // 狭い幅ならパネルを閉じる
    if (mobileQuery.matches)
        closeCommentPanel();
    // 行を包む閉じた節は、行を探す前に開く（閉じた節の中の行は隠れていて探せない）
    if (comment.startLine != null)
        sourceLineElements(comment.startLine).forEach((el) => revealSection(el));
    const element = comment.startLine != null ? lineElement(comment.startLine) : null;
    // 見つからない・今の見せ方で隠れている場合、通知を出す
    if (!element) {
        showToast(COMMENT_LABELS.lineHidden);
        return;
    }
    element.scrollIntoView({ block: "center" });
    element.classList.add("line-flash");
    window.setTimeout(() => element.classList.remove("line-flash"), FLASH_MS);
}
/** コメントの場所の見出しへ移り、見出しを一時だけ目立たせる（見出しが無いコメントはページの先頭へ移る） */
function jumpToHeading(comment) {
    // コメントのページが今のページでなければ、そのページを見出しの断片付き（無ければ断片なし）で開いて終わる
    const target = new URL(comment.page, window.location.href);
    if (`${target.pathname}${target.search}` !== currentPageUrl()) {
        target.hash = comment.headingId ?? "";
        navigateWithin(target.href);
        return;
    }
    // 狭い幅ならパネルを閉じる
    if (mobileQuery.matches)
        closeCommentPanel();
    const heading = comment.headingId ? document.getElementById(comment.headingId) : null;
    // 見出しが無いコメントはページの先頭へ移る
    if (!heading) {
        window.scrollTo({ top: 0 });
        return;
    }
    // 見出しを包む閉じた節を開いてから移り、一時だけ目立たせる
    revealSection(heading);
    heading.scrollIntoView({ block: "center" });
    heading.classList.add("line-flash");
    window.setTimeout(() => heading.classList.remove("line-flash"), FLASH_MS);
}
/** Pages のヘッダーのコメントのボタンに、パネルを開く動きと溜めた数を紐付ける */
function bindHeaderCommentButton() {
    const button = document.querySelector(".topbar [data-comment-open]");
    if (!button)
        return;
    renderCommentButton(loadComments().length);
    syncHeaderCommentButton(false);
    // 押下で書く枠を出さずにパネルを開く
    button.addEventListener("click", () => openCommentPanel());
}
/** 今のページのコメントを付けた行ごとに、本文の区画の右の余白へ行のマークを置く */
function renderLineMarkers() {
    const article = document.querySelector(".markdown-body");
    if (!article || !document.body.dataset.sourcePath)
        return;
    // 置いてある行のマークを外す
    article.querySelectorAll(":scope > .line-marker").forEach((marker) => marker.remove());
    // 今のページのコメントを始めの行でまとめる
    const byLine = new Map();
    loadComments().filter((c) => c.page === currentPageUrl() && c.startLine != null).forEach((c) => {
        if (!byLine.has(c.startLine))
            byLine.set(c.startLine, []);
        byLine.get(c.startLine).push(c);
    });
    byLine.forEach((comments, line) => {
        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = "line-marker";
        marker.dataset.markerLine = String(line);
        marker.setAttribute("aria-label", `この行のコメント ${comments.length} 件`);
        marker.innerHTML = `<svg viewBox="0 0 22 20" aria-hidden="true"><path d="M1 1h20v13H9l-5 5v-5H1z"/></svg><span>${numberFormat.format(comments.length)}</span>`;
        // 1 件ならそのコメントへ移ってパネルを開き、2 件以上なら移る先を選ぶメニューを開く
        marker.addEventListener("click", (event) => {
            event.stopPropagation();
            if (comments.length === 1) {
                openCommentPanel({ focusId: comments[0].id });
                return;
            }
            openLineMarkerMenu(marker, comments);
        });
        article.appendChild(marker);
    });
    // 位置を合わせる
    positionLineMarkers();
}
/** 同じ行のコメントから移る先を選ぶメニューを、行のマークの下に開く */
function openLineMarkerMenu(marker, comments) {
    let menu = document.getElementById("line-marker-menu");
    if (!menu) {
        menu = document.createElement("div");
        menu.id = "line-marker-menu";
        menu.className = "line-marker-menu";
        menu.setAttribute("popover", "");
        document.body.appendChild(menu);
        menu.addEventListener("click", (event) => {
            const id = event.target.closest("[data-goto-comment]")?.dataset.gotoComment;
            if (!id)
                return;
            menu.hidePopover();
            openCommentPanel({ focusId: id });
        });
    }
    menu.innerHTML = `<p class="line-marker-menu-head">${COMMENT_LABELS.markerMenu.replace("{count}", String(comments.length))}</p>
    <ul>${comments.map((c) => `<li><button type="button" data-goto-comment="${escapeHtml(c.id)}">${escapeHtml(shortenQuote(c.body))}</button></li>`).join("")}</ul>`;
    const rect = marker.getBoundingClientRect();
    menu.style.top = `${rect.bottom + 4}px`;
    menu.style.left = `${Math.max(8, rect.right - 280)}px`;
    menu.showPopover();
}
/** 行のマークの高さを、それぞれの行の今の位置に合わせ直す */
function positionLineMarkers() {
    const article = document.querySelector(".markdown-body");
    if (!article)
        return;
    const top = article.getBoundingClientRect().top;
    article.querySelectorAll(":scope > .line-marker").forEach((marker) => {
        const element = lineElement(marker.dataset.markerLine);
        // 行が隠れている場合、行のマークも隠す
        marker.hidden = !element;
        if (!element)
            return;
        const rect = element.getBoundingClientRect();
        marker.style.top = `${rect.top - top + rect.height / 2}px`;
    });
}
/** 同じ配信の中へ移る間だけ立て、離脱の確認を出さない印 */
let movingWithin = false;
/** 行き先が同じ配信の中の別の文書（オリジンが同じで、パスが data-site-root の下にあり、パスかクエリ文字列が今のページと違う）か。断片だけが違うときはページを離れない */
function isOtherDocumentWithin(url) {
    const siteRoot = document.body.dataset.siteRoot || "/";
    return url.origin === window.location.origin
        && decodeURIComponent(url.pathname).startsWith(decodeURIComponent(siteRoot))
        && `${url.pathname}${url.search}` !== currentPageUrl();
}
/** スクリプトから別のページへ移る。同じ配信の中の別の文書へ移るときは、離脱の確認を出さない印を立ててから移る */
function navigateWithin(href) {
    // 同じ配信の中の別の文書へ移る場合だけ印を立てる（断片だけが違うと印が残り、後でタブを閉じても確認が出なくなる。違うオリジンと data-site-root の外はコピーしていないコメントがあれば確認が出る）
    if (isOtherDocumentWithin(new URL(href, window.location.href)))
        movingWithin = true;
    window.location.href = href;
}
/** コピーしていないコメントがあるままタブを閉じる・再読み込みするときに、離脱の確認を出す */
function bindLeaveGuard() {
    // 同じ配信の中の別の文書へのリンクの押下で、離脱の確認を出さない印を立てる
    window.addEventListener("click", (event) => {
        const link = event.target.closest?.("a[href]");
        if (!link || event.defaultPrevented || (link.target && link.target !== "_self"))
            return;
        if (isOtherDocumentWithin(new URL(link.href, window.location.href)))
            movingWithin = true;
    });
    window.addEventListener("beforeunload", (event) => {
        if (movingWithin || !loadComments().some((c) => !c.copied))
            return;
        event.preventDefault();
        event.returnValue = "";
    });
}
/** 元の行・入口・行のマーク・離脱の確認をまとめて紐付ける（Pages では元の行と行のマークを飛ばし、ヘッダーのコメントのボタンを紐付ける） */
function bindComments(article) {
    const hasSource = Boolean(document.body.dataset.sourcePath);
    // 元のファイルもトップバーのコメントのボタンも持たないページでは何もしない
    if (!hasSource && !document.querySelector(".topbar [data-comment-open]"))
        return;
    if (hasSource) {
        applySourceLines(article);
        bindCommentEntry(article);
        renderLineMarkers();
        bindLeaveGuard();
        // 本文の大きさの変化と幅の変化で行のマークの位置を合わせ直す
        new ResizeObserver(() => positionLineMarkers()).observe(article);
        window.addEventListener("resize", positionLineMarkers);
    }
    else {
        bindCommentEntry(article);
        bindLeaveGuard();
        bindHeaderCommentButton();
    }
    // Esc でコメントのパネルを閉じる
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape")
            closeCommentPanel();
    });
    // URL の断片が #L{行} なら、その行へ移る
    const line = hasSource ? /^#L(\d+)$/.exec(window.location.hash)?.[1] : undefined;
    if (line)
        jumpToLine({ page: currentPageUrl(), startLine: Number(line) });
}
/* ============================================================================
 * 23. 開発ドキュメントサーバー: 行の詳細
 * 生成した Markdown が表の後ろに置いた行の詳細（小見出しと小さな表）を親の行の下へ組み替え、行の開閉とすべて開くを付ける。
 * 行の詳細のマークの無いページでは何もしない
 * ---------------------------------------------------------------------------- */
/* 行の詳細で利用者の目に触れる文言 */
const ROW_DETAIL_LABELS = {
    expandAll: "すべて開く",
    collapseAll: "すべて閉じる",
    more: "ほか {count} 件",
    showAll: "全体を見る",
    count: "件数",
};
/* 大きな値の配列のうち行の詳細に出す先頭の件数（4 件以上の配列を先頭 3 件に縮める） */
const LARGE_VALUE_HEAD = 3;
/* 行の開閉のシェブロン（線のアイコン。飾りなので読み上げから外す） */
const ROW_CHEVRON = '<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
/* 大きな値の全体（全体を見るボタン → 配列・見出し・置き場所） */
const largeValues = new WeakMap();
/** 親の行の直後にある行の詳細の行を返す（無ければ null） */
function rowDetailOf(row) {
    const next = row.nextElementSibling;
    return row.dataset.detail && next?.classList.contains("row-detail") ? next : null;
}
/** 行の詳細のマークの属性を読む（行の位置が 0 以上の整数でなければ null） */
function readRowDetailMeta(element) {
    const index = Number(element.dataset.index);
    if (!Number.isInteger(index) || index < 0)
        return null;
    return { table: element.dataset.table || "", index, field: element.dataset.field || "" };
}
/** 本文の行の詳細のマークごとに、続く小見出しと小さな表を親の表の行の直後の行の詳細へ組み替える */
function buildRowDetails(article) {
    const marks = [...article.querySelectorAll("div.row-detail-meta")];
    // マークが無いページでは何もしない
    if (marks.length === 0)
        return;
    const place = rowDetailPlace();
    // 親の表ごとの、行の詳細を差し込む前の行の並び（行の位置は差し込む前の並びで数える）
    const parents = new Map();
    marks.forEach((mark) => {
        // 読めない・直後に小見出しと表が続かない場合、そのマークは飛ばす
        const meta = readRowDetailMeta(mark);
        const heading = mark.nextElementSibling;
        const subTable = heading?.nextElementSibling;
        if (!meta || !/^H[1-6]$/.test(heading?.tagName || "") || subTable?.tagName !== "TABLE")
            return;
        // 親の表: マークから手前の兄弟を遡り、先に組み替えた組の残り（マーク・小見出し）を飛ばした最初の表
        let parent = mark.previousElementSibling;
        while (parent && parent.tagName !== "TABLE")
            parent = parent.previousElementSibling;
        if (parent?.tBodies[0] && !parents.has(parent))
            parents.set(parent, [...parent.tBodies[0].rows]);
        const row = parents.get(parent)?.[meta.index];
        // 親の表の本体に行の位置の行が無い場合、そのマークは飛ばす
        if (!row)
            return;
        const label = heading.textContent.trim();
        const rowName = label.includes(" の") ? label.slice(0, label.indexOf(" の")) : label;
        // 小さな表に印を付け、小見出しの文言を caption にし、大きな値を縮める
        subTable.classList.add("sub-table");
        const caption = document.createElement("caption");
        caption.textContent = label;
        subTable.prepend(caption);
        shortenLargeValues(subTable, rowName, `${place} › ${rowName}`);
        // 同じ行の 2 つ目以降の入れ子の表は、既にある行の詳細の中へ項目の順に並べる（ボタンは 1 つ）
        let detail = rowDetailOf(row);
        if (!detail) {
            const id = `row-detail-${meta.table.replace(/[^\w-]/g, "_")}-${marks.indexOf(mark)}`;
            detail = document.createElement("tr");
            detail.className = "row-detail";
            detail.innerHTML = `<td colspan="${parent.tHead?.rows[0]?.cells.length || row.cells.length}"><div class="row-detail-body" id="${id}" hidden="until-found"><div class="row-detail-inner"></div></div></td>`;
            row.dataset.detail = id;
            row.classList.add("parent-row");
            row.after(detail);
            const button = placeRowToggle(row, id, label);
            // 閉じた中身がページ内検索かテキストの断片で見つかったら、その行を開いた状態にする
            detail.querySelector(".row-detail-body").addEventListener("beforematch", () => setRowOpen(button, true));
        }
        detail.querySelector(".row-detail-inner").append(subTable);
        // マークと小見出しを本文から消す
        mark.remove();
        heading.remove();
    });
    // 行の詳細を持つ表の、行の詳細を持たない行の先頭のセルに、ボタンの幅の空きを置いて名前の位置を揃える
    parents.forEach((rows) => {
        // 行の詳細を 1 つも持たない表（マークが全て飛ばされた表）は揃えない
        if (!rows.some((row) => row.dataset.detail))
            return;
        rows.forEach((row) => {
            if (row.dataset.detail || !row.cells[0])
                return;
            const cell = row.cells[0];
            const lead = document.createElement("span");
            lead.className = "row-lead";
            lead.innerHTML = '<span class="row-toggle-spacer"></span>';
            lead.append(...cell.childNodes);
            cell.append(lead);
        });
    });
}
/** 大きな値の置き場所（`{種別} › {設計書}`）を、ページの元のパスから組み立てる */
function rowDetailPlace() {
    const source = document.body.dataset.sourcePath || "";
    const path = source.replace(/^dev\/設計書\//, "").replace(/\.yaml$/, "");
    return path.split("/").filter(Boolean).join(" › ") || document.querySelector(".markdown-body h1")?.textContent.trim() || "";
}
/** 行の先頭のセルの頭に、行の詳細を開閉するシェブロンのボタンを置く */
function placeRowToggle(row, detailId, label) {
    const cell = row.cells[0];
    const lead = document.createElement("span");
    lead.className = "row-lead";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "row-toggle";
    button.innerHTML = ROW_CHEVRON;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-controls", detailId);
    button.setAttribute("aria-expanded", "false");
    lead.append(button, ...cell.childNodes);
    cell.append(lead);
    // 押下を行の押下（狭い幅の最終列の畳み）へ伝えずに、行の詳細を反転する
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        setRowOpen(button, button.getAttribute("aria-expanded") !== "true");
    });
    return button;
}
/** 行の開閉ボタンと行の詳細を、開いた状態か閉じた状態にそろえる */
function setRowOpen(button, open) {
    const body = document.getElementById(button.getAttribute("aria-controls"));
    const parentRow = button.closest("tr");
    button.setAttribute("aria-expanded", String(open));
    // 閉じるときは hidden="until-found" に戻し、ページ内検索で見つかれば開くようにする
    if (open)
        body.removeAttribute("hidden");
    else
        body.setAttribute("hidden", "until-found");
    parentRow.classList.toggle("is-expanded", open);
    body.closest("tr").classList.toggle("is-expanded", open);
    syncExpandAll(parentRow.closest("table"));
}
/** 行の開閉ボタンを持つ表ごとに、表の上の操作の並びへすべて開くボタンを置く */
function bindExpandAll(article) {
    article.querySelectorAll("table:not(.sub-table)").forEach((table) => {
        if (!table.querySelector("tbody .row-toggle"))
            return;
        const frame = table.closest(".table-frame") || table;
        // 表の上の操作の並びが無ければ作って表の外枠の前に置く
        let tools = (frame.previousElementSibling?.matches(".table-tools") ? frame.previousElementSibling : null);
        if (!tools) {
            tools = document.createElement("div");
            tools.className = "table-tools";
            frame.before(tools);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ghost expand-all";
        button.textContent = ROW_DETAIL_LABELS.expandAll;
        // 表の絞り込み欄と表示する列のボタンの間に置く
        const toggle = tools.querySelector(".column-toggle");
        if (toggle)
            toggle.before(button);
        else
            tools.append(button);
        // 全て開いていれば全て閉じ、そうでなければ絞り込みで出している行の詳細を全て開く
        button.addEventListener("click", () => {
            const toggles = [...table.querySelectorAll("tbody .row-toggle")];
            const open = !toggles.every((b) => b.getAttribute("aria-expanded") === "true");
            toggles
                .filter((b) => !open || !b.closest("tr").classList.contains("hidden"))
                .forEach((b) => setRowOpen(b, open));
        });
    });
}
/** 表のすべて開くボタンの文言を、今の開き具合に合わせる */
function syncExpandAll(table) {
    const frame = table.closest(".table-frame") || table;
    const button = frame.previousElementSibling?.querySelector(".expand-all");
    if (!button)
        return;
    const allOpen = [...table.querySelectorAll("tbody .row-toggle")].every((b) => b.getAttribute("aria-expanded") === "true");
    button.textContent = allOpen ? ROW_DETAIL_LABELS.collapseAll : ROW_DETAIL_LABELS.expandAll;
}
/** JSON の値の中で最初に見つかった、先頭の件数より多い配列を返す（無ければ null） */
function findLargeArray(value) {
    if (Array.isArray(value)) {
        if (value.length > LARGE_VALUE_HEAD)
            return value;
        for (const item of value) {
            const found = findLargeArray(item);
            if (found)
                return found;
        }
        return null;
    }
    if (value && typeof value === "object") {
        for (const item of Object.values(value)) {
            const found = findLargeArray(item);
            if (found)
                return found;
        }
    }
    return null;
}
/** 小さな表の大きな値を先頭の件数に縮め、残りの件数と全体を見るボタンを添える */
function shortenLargeValues(table, rowName, place) {
    [...table.tBodies[0]?.rows || []].forEach((row) => {
        const name = row.cells[0]?.textContent.trim() || "";
        [...row.cells].slice(1).forEach((cell) => {
            // 文字列を JSON として読み、先頭の件数より多い配列が無ければそのセルは変えない
            let value;
            try {
                value = JSON.parse(cell.textContent.trim());
            }
            catch {
                return;
            }
            const large = findLargeArray(value);
            if (!large)
                return;
            const whole = [...large];
            large.splice(LARGE_VALUE_HEAD);
            const code = document.createElement("code");
            code.textContent = JSON.stringify(value);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ghost value-more";
            button.textContent = ROW_DETAIL_LABELS.showAll;
            largeValues.set(button, { values: whole, title: `${rowName} の ${name}`, place });
            cell.replaceChildren(code, ` ${ROW_DETAIL_LABELS.more.replace("{count}", numberFormat.format(whole.length - LARGE_VALUE_HEAD))}`, button);
        });
    });
}
/** 全体を見るボタンの押下で、項目の要点パネルに大きな値の全体を番号つきで出す */
function bindLargeValues(article) {
    article.addEventListener("click", (event) => {
        const button = event.target.closest(".value-more");
        const large = button && largeValues.get(button);
        if (!large)
            return;
        openItemPanel({
            title: large.title,
            place: large.place,
            fields: [
                [ROW_DETAIL_LABELS.count, `${numberFormat.format(large.values.length)} 件`],
                ...large.values.map((value, index) => [String(index + 1), typeof value === "string" ? value : JSON.stringify(value)]),
            ],
        }, button, "");
    });
}
/* ============================================================================
 * 24. 見出しの節の開閉
 * 本文の h2〜h4 を押して、次の同じか上の階層の見出しの手前までの節を開閉する。
 * 既定の開閉は、見出しの直後の `<!-- section: closed -->` / `<!-- section: open -->` が決め、無ければ登録した見出し名が決める
 * ---------------------------------------------------------------------------- */
/* ページを開いた時点で節を閉じる見出し。`#` の数が階層、空白の後ろが見出し名 */
const CLOSED_SECTION_HEADINGS = [
    "#### セットアップ",
    "#### フロー",
    "#### 期待値",
    "#### 単体テスト",
    "### 補足",
    "### 記述例",
    "### 異常系",
];
/* 見出しの直後のコメントから `section:` の値を取り出す */
const SECTION_DIRECTIVE_PATTERN = /^\s*section:\s*(\S+)\s*$/;
/* 開閉の矢印。開いているときは下を向く */
const SECTION_CHEVRON = '<svg class="section-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
/** 開閉を付けた見出しの一覧。節の入れ物は見出し（と警告）の直後に置く */
const sectionToggles = [];
/** 見出しの直後の `<!-- section: ... -->` から、既定の開閉の指定を読む */
function readSectionDirective(heading) {
    // 空白だけの文字列を飛ばして、最初に当たった節点を見る
    let node = heading.nextSibling;
    while (node && node.nodeType === Node.TEXT_NODE && !node.textContent.trim())
        node = node.nextSibling;
    if (!node || node.nodeType !== Node.COMMENT_NODE)
        return null;
    const value = SECTION_DIRECTIVE_PATTERN.exec(node.textContent)?.[1];
    if (value === undefined)
        return null;
    return { kind: value === "closed" || value === "open" ? value : "unknown", value };
}
/** 見出しの文言を、見出しアンカーを除いて返す */
function headingText(heading) {
    const copy = heading.cloneNode(true);
    copy.querySelector(".heading-anchor")?.remove();
    return copy.textContent.trim();
}
/** 見出しが、階層と名前で既定で閉じる見出しに当たるかを返す */
function matchesClosedHeading(heading) {
    const level = Number(heading.tagName[1]);
    const text = headingText(heading);
    return CLOSED_SECTION_HEADINGS.some((entry) => {
        const space = entry.indexOf(" ");
        const marks = entry.slice(0, space);
        const name = entry.slice(space + 1);
        // 同じ階層で、名前が同じか、名前の直後が全角の「（」で始まる
        return marks.length === level && (text === name || text.startsWith(`${name}（`));
    });
}
/** 知らない値を書いたことを書き手へ知らせる警告を作る（値はページの本文から来るので文字列として入れる） */
function buildSectionWarning(value) {
    const warning = document.createElement("div");
    warning.className = "callout callout-warn";
    const title = document.createElement("div");
    title.className = "callout-title";
    title.textContent = "開閉の指定を読めません";
    const message = document.createElement("p");
    message.textContent = `<!-- section: ${value} --> の ${value} は使えない値です。closed か open を書いてください。この節は設定どおりに開閉します。`;
    warning.append(title, message);
    return warning;
}
/** 節の開閉を状態に合わせる。閉じた節の中身は、ページ内検索で当たるよう `until-found` で隠す */
function applySectionState({ button, body }, open) {
    button.setAttribute("aria-expanded", String(open));
    if (open)
        body.removeAttribute("hidden");
    else
        body.setAttribute("hidden", "until-found");
}
/** 閉じた見出しに同じ階層の閉じた見出しが続くときだけ、後の見出しに印を付け直し、行のマークの位置を合わせ直す */
function refreshSectionLayout() {
    sectionToggles.forEach(({ heading, body }) => {
        let before = heading.previousElementSibling;
        // 開いている節は、末尾の中身まで降りて見る
        while (before?.matches(".section-body:not([hidden])") && before.lastElementChild)
            before = before.lastElementChild;
        const closedBefore = sectionToggles.find((s) => s.body === before && s.body.hasAttribute("hidden"));
        const sameLevel = closedBefore?.heading.tagName === heading.tagName;
        heading.classList.toggle("after-closed", body.hasAttribute("hidden") && sameLevel);
    });
    positionLineMarkers();
}
/** 要素を包む閉じた節と閉じた範囲の折りたたみを外側まで全て開き、要素を包むタブを選ぶ */
function revealSection(target) {
    const closed = sectionToggles.filter(({ body }) => body.hasAttribute("hidden") && body.contains(target));
    if (closed.length > 0) {
        closed.forEach((section) => applySectionState(section, true));
        refreshSectionLayout();
    }
    for (let fold = target.closest("details.table-fold"); fold; fold = fold.parentElement?.closest("details.table-fold") ?? null) {
        fold.open = true;
    }
    selectTabOf(target);
}
/** URL の断片（`#` 付き）が指す要素を返す。符号化が壊れていれば要素は無いものとして扱う */
function fragmentTarget(fragment) {
    try {
        return document.getElementById(decodeURIComponent(fragment.slice(1)));
    }
    catch (e) {
        console.warn("URL の断片をデコードできません", fragment, e);
        return null;
    }
}
/** 本文の h2〜h4 を、押すと節を開閉する見出しにし、既定の開閉を決める */
function enableSectionToggles(article) {
    const headings = [...article.querySelectorAll(ANCHORED_HEADINGS)];
    // 文書の後ろから見る（深い節を先に包んでから、浅い節で包む）
    for (let index = headings.length - 1; index >= 0; index--) {
        const heading = headings[index];
        const level = Number(heading.tagName[1]);
        // 既定の開閉を決める。知らない値は見出しの下に警告を置き、指定が無いときと同じく決める
        const directive = readSectionDirective(heading);
        const closedByDefault = directive && directive.kind !== "unknown" ? directive.kind === "closed" : matchesClosedHeading(heading);
        let start = heading;
        if (directive?.kind === "unknown") {
            start = buildSectionWarning(directive.value);
            heading.after(start);
        }
        // 見出し（と警告）の直後から、次の同じか上の階層の見出しの手前までを、節の入れ物へ移す
        const body = document.createElement("div");
        body.className = "section-body";
        body.id = `section-body-${index}`;
        let node = start.nextSibling;
        while (node) {
            const next = node.nextSibling;
            if (node instanceof Element && /^H[1-6]$/.test(node.tagName) && Number(node.tagName[1]) <= level)
                break;
            // 本文の直下に置く行のマークは移さない
            if (!(node instanceof Element && node.matches(".line-marker")))
                body.appendChild(node);
            node = next;
        }
        start.after(body);
        // 見出しの文言と矢印を開閉のボタンで包む。見出しアンカーはボタンの外にリンクのまま残す
        const anchor = heading.querySelector(":scope > .heading-anchor");
        const label = document.createElement("span");
        label.className = "section-label";
        [...heading.childNodes].filter((node) => node !== anchor).forEach((node) => label.appendChild(node));
        const button = document.createElement("button");
        button.type = "button";
        button.className = "section-toggle";
        button.setAttribute("aria-controls", body.id);
        button.append(label);
        button.insertAdjacentHTML("beforeend", SECTION_CHEVRON);
        heading.prepend(button);
        const section = { heading, button, body };
        applySectionState(section, !closedByDefault);
        button.addEventListener("click", () => {
            applySectionState(section, body.hasAttribute("hidden"));
            refreshSectionLayout();
        });
        sectionToggles.push(section);
    }
    refreshSectionLayout();
    // ページ内検索で閉じた節の中に当たってブラウザが開いたとき、見出しの状態を合わせる
    article.addEventListener("beforematch", (event) => {
        const section = sectionToggles.find(({ body }) => body === event.target);
        if (!section)
            return;
        applySectionState(section, true);
        refreshSectionLayout();
    });
    // 目次・本文のリンクで閉じた節の中の見出しへ移るときは、移る前に節を開く
    document.addEventListener("click", (event) => {
        const link = event.target.closest?.('a[href^="#"]');
        const target = link && fragmentTarget(link.getAttribute("href"));
        if (target)
            revealSection(target);
    }, true);
    // URL の見出しの指定へ移るとき、包む節を開いてから移る（開いた直後は着地の位置がずれるので移り直す）
    // 機能を付けた表の行なら、絞り込みで隠れていれば絞り込みを解除し、上のヘッダーと表の見出し行の下に隠れないよう画面の中ほどへ送る
    const revealFragment = () => {
        const target = fragmentTarget(window.location.hash);
        if (!target)
            return;
        revealSection(target);
        if (isTableRowTarget(target)) {
            clearRowFilters(target);
            target.scrollIntoView({ block: "center" });
        }
        else {
            target.scrollIntoView();
        }
    };
    window.addEventListener("hashchange", revealFragment);
    revealFragment();
    // 読み込みの終わりにブラウザが断片の行き先の行を画面の上端へ送り直すので、行のときはその後にもう一度送る
    if (document.readyState !== "complete") {
        window.addEventListener("load", () => window.requestAnimationFrame(() => {
            if (isTableRowTarget(fragmentTarget(window.location.hash)))
                revealFragment();
        }), { once: true });
    }
}
/** 要素が、機能を付けた表の本体の行か */
function isTableRowTarget(target) {
    return target instanceof HTMLTableRowElement && tableStates.has(target.closest("table"));
}
/* 部品ごとに書けるキー */
const DOC_PART_KEYS = {
    tabs: ["group", "title"],
    steps: ["title"],
};
/* 選んだタブ名を `group` ごとに残す保存領域のキーの頭（キーは `{頭}{group}`、値は選んだタブ名） */
const TAB_STORAGE_PREFIX = "docs-tabs:";
/* 本文の部品で利用者の目に触れる文言（`{名前}` は埋める値、`{choices}` は使える指定を `・` でつないだもの） */
const DOC_PART_LABELS = {
    tabsWarnTitle: "タブの指定を読めません",
    stepsWarnTitle: "ステップの指定を読めません",
    noHeading: "範囲の中にタブ名にする見出しがありません。タブごとに見出し（### など）を書いてください。この範囲はタブにせずに表示します。",
    noOrderedList: "範囲の中にステップにする番号付きリストがありません。1. で始まるリストを包んでください。この範囲はステップにせずに表示します。",
    unknownKey: "{value}= は使えないキーです。{choices} のどれかを書いてください。",
    unknownWord: "{value} は使えない指定です。{choices} のどれかを書いてください。",
    missingEnd: "<!-- /{name} --> がありません。この指定を、同じ区切りの最後までに当てています。",
    conflictingFold: "closed と open が両方書かれています。後に書いた {value} で表示します。",
    tabsFold: "タブ（{names}）",
    tabsFoldEmpty: "タブ",
    stepsFold: "手順（{n} ステップ）",
    tablistName: "{names} の切り替え",
    treeWarnTitle: "ファイルツリーを読めません",
    treeTooDeep: "{line} 行目の罫線が、上の行より 2 段以上深い位置にあります。罫線の段を 1 段ずつ下げて書いてください。このツリーはコードのまま表示します。",
    treeNoBranch: "{line} 行目に ├── か └── がありません。罫線の後ろに ├── か └── を続けてください。このツリーはコードのまま表示します。",
    treeName: "ファイルツリー",
    marksWarnTitle: "コードの行の印を読めません",
    unknownMark: "{line} 行目の [!code {name}] は使えない印です。{choices} のどれかを書いてください。この行は印を当てずに表示します。",
    lineAdd: "追加:",
    lineDel: "削除:",
};
/* タブ名を並べるときの区切り */
const TAB_NAME_SEPARATOR = "・";
/* タブのキー操作で隣のタブへ移る矢印キー（値は進む向き） */
const TAB_ARROW_STEPS = { ArrowRight: 1, ArrowLeft: -1 };
/* ファイルツリーにするコードブロックの言語指定 */
const FILE_TREE_LANG = "tree";
/* ファイルツリーの罫線: 1 段分（親の行が続くときの縦線と空白 3 つ、続かないときの空白 4 つ）・項目の頭・名前の後ろの注釈（空白の後の `←` か `#` から後ろ） */
const FILE_TREE_PATTERNS = {
    indent: /^(?:│ {3}| {4})/,
    branch: /^(?:├── |└── )/,
    note: /^(.+?)\s+(?:←|#)\s+(.+)$/,
};
/* ファイルツリーのフォルダとファイルの線のアイコン */
const FILE_TREE_ICONS = {
    folder: '<svg class="icon file-tree-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    file: '<svg class="icon file-tree-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6zM14 3v4h4"/></svg>',
};
/* コードの行末の印の書き出し */
const CODE_MARK_HEAD = "[!code ";
/* コードの行末の印と、行に付ける種類・行頭の記号・読み上げにだけ届く文言（強調は記号も文言も持たない） */
const CODE_LINE_MARKS = {
    "++": { kind: "add", sign: "+", spoken: DOC_PART_LABELS.lineAdd },
    "--": { kind: "del", sign: "-", spoken: DOC_PART_LABELS.lineDel },
    highlight: { kind: "highlight", sign: "", spoken: "" },
};
/* コードの行の印の読み取り: 行末の印・打ち消した印（`[` の後ろに `\`）・印だけを持っていた行コメントの頭 */
const CODE_MARK_PATTERNS = {
    mark: /\[!code ([^\]]*)\]\s*$/,
    escaped: /\[\\!code /g,
    commentLeader: /(?:#|\/\/|--|;|%|\/\*|<!--)\s*$/,
};
/* 行に分けないコードブロックの言語指定（描いた表示・図・ファイルツリーにするもの） */
const CODE_MARK_SKIP_LANGS = ["markdown", "md", "mermaid", FILE_TREE_LANG];
/* バッジにするインラインコードの頭と、打ち消しの頭（`\` を外して残す） */
const BADGE_PREFIXES = { badge: "badge:", escaped: "badge\\:" };
/* タブ・タブの中身の識別子を振る連番（見出しに識別子が無いときだけ使う） */
let docTabSeq = 0;
/** 本文のタブとステップの範囲、ファイルツリー・コードの行の印・バッジを組み立て、タブのページ内検索を紐付ける（見出しアンカーの後、見出しの開閉と目次・コードのコピーより前に呼ぶ） */
function enhanceDocParts(article) {
    readRangeDirectives(article, "tabs").forEach(buildTabs);
    readRangeDirectives(article, "steps").forEach(buildSteps);
    buildFileTrees(article);
    buildCodeMarks(article);
    buildBadges(article);
    // タブの中身でページ内検索が当たったとき、そのタブを選ぶ
    article.addEventListener("beforematch", (event) => selectTabOf(event.target));
}
/** 範囲の引数から、部品で使えるキーと値・折りたたみ・警告を決める（使えない指定はその指定だけを当てずに警告へ回す） */
function resolveDocPartSetup({ range, part }) {
    const { args } = range;
    const allowed = DOC_PART_KEYS[part];
    const choices = [...allowed.map((key) => `${key}=`), ...RANGE_FOLD_WORDS].join("・");
    const warnings = [];
    if (!range.end)
        warnings.push(formatLabel(DOC_PART_LABELS.missingEnd, { name: part }));
    const keys = {};
    args.keys.forEach(([key, value]) => {
        if (allowed.includes(key))
            keys[key] = value;
        else
            warnings.push(formatLabel(DOC_PART_LABELS.unknownKey, { value: key, choices }));
    });
    // 種類・足す機能・外す機能の書き方は、この部品では使えない
    [...args.kinds, ...args.add.map((word) => `+${word}`), ...args.remove.map((word) => `-${word}`)].forEach((value) => {
        warnings.push(formatLabel(DOC_PART_LABELS.unknownWord, { value, choices }));
    });
    if (new Set(args.folds).size > 1)
        warnings.push(formatLabel(DOC_PART_LABELS.conflictingFold, { value: args.fold }));
    return { keys, fold: args.fold, warnings };
}
/** 範囲の上に警告を置き、折りたたみの指定があれば範囲を折りたたみに入れる */
function finishDocPart({ range, setup, warnings, warnTitle, foldSummary }) {
    if (warnings.length)
        range.start.after(buildTableWarning(warnTitle, warnings));
    if (setup.fold)
        foldTableRange(range, setup.keys.title || foldSummary);
}
/** 範囲 1 つをタブの並びとタブの中身にする */
function buildTabs(range) {
    const setup = resolveDocPartSetup({ range, part: "tabs" });
    const warnings = [...setup.warnings];
    const headings = range.nodes.filter((node) => /^H[2-6]$/.test(node.tagName));
    // タブ名にする見出しが無ければ、タブにせず警告だけを置く
    if (headings.length === 0) {
        warnings.push(DOC_PART_LABELS.noHeading);
        finishDocPart({ range, setup, warnings, warnTitle: DOC_PART_LABELS.tabsWarnTitle, foldSummary: DOC_PART_LABELS.tabsFoldEmpty });
        return;
    }
    // 範囲の中で最初に出る見出しの階層でタブに区切る
    const level = headings[0].tagName;
    const tablist = tableEl("div", { class: "doc-tablist", role: "tablist" });
    const container = tableEl("div", { class: "doc-tabs" }, [tablist]);
    if (setup.keys.group)
        container.dataset.group = setup.keys.group;
    headings[0].before(container);
    let panel = null;
    const names = [];
    // 最初の見出しより前の要素はタブの外に残し、見出しからは次の同じ階層の見出しまでを中身へ移す（コメントと空白も、節の開閉の指定が見出しの直後に残るよう一緒に移す）
    for (let node = headings[0]; node && node !== range.end;) {
        const next = node.nextSibling;
        if (node instanceof HTMLElement && node.tagName === level) {
            panel = createTab({ heading: node, tablist, container, names });
        }
        else if (panel) {
            panel.append(node);
        }
        node = next;
    }
    // 見出しの文言と識別子を持つタブに置き換えた見出しを、本文の見出しから外す
    headings.filter((heading) => heading.tagName === level).forEach((heading) => heading.remove());
    tablist.setAttribute("aria-label", formatLabel(DOC_PART_LABELS.tablistName, { names: names.join(TAB_NAME_SEPARATOR) }));
    // 開いた時点の選択は、group が残した選択のタブ。無ければ先頭（残すのは利用者の操作だけ）
    const saved = setup.keys.group ? loadTabChoice(setup.keys.group) : null;
    showTabAt(container, Math.max(0, names.indexOf(saved ?? "")));
    bindTabKeys(tablist);
    finishDocPart({ range, setup, warnings, warnTitle: DOC_PART_LABELS.tabsWarnTitle, foldSummary: formatLabel(DOC_PART_LABELS.tabsFold, { names: names.join(TAB_NAME_SEPARATOR) }) });
}
/** 見出し 1 つからタブとタブの中身を作って並べ、中身を返す（見出しの識別子はタブが引き継ぐ） */
function createTab({ heading, tablist, container, names }) {
    const name = headingText(heading);
    const id = heading.id || `doc-tab-${docTabSeq++}`;
    const panel = tableEl("div", { class: "doc-tabpanel", role: "tabpanel", id: `${id}-panel`, tabindex: "0", "aria-labelledby": id });
    const tab = tableEl("button", {
        type: "button",
        class: "doc-tab",
        role: "tab",
        id,
        text: name,
        "aria-controls": panel.id,
    });
    tab.dataset.name = name;
    // タブの中身の先頭へ戻す見出しの階層（戻すのは目次と節の開閉を組み立てた後）
    tab.dataset.level = heading.tagName.toLowerCase();
    tab.addEventListener("click", () => selectTab({ tab, save: true }));
    tablist.append(tab);
    container.append(panel);
    names.push(name);
    return panel;
}
/** 並びの左右の矢印キーで隣のタブへ入力を移して選ぶ（端から反対の端へ回り込む） */
function bindTabKeys(tablist) {
    tablist.addEventListener("keydown", (event) => {
        const step = TAB_ARROW_STEPS[event.key];
        const tab = event.target.closest(".doc-tab");
        if (!step || !tab)
            return;
        event.preventDefault();
        const tabs = tabsOf(tablist.closest(".doc-tabs"));
        const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
        selectTab({ tab: next, save: true });
        next.focus();
    });
}
/** タブの並びのタブを、並びの順に返す */
function tabsOf(container) {
    return [...container.querySelectorAll(":scope > .doc-tablist > .doc-tab")];
}
/** 並びの index 番目のタブを選んだ状態にし、他のタブの中身を隠す（隠した中身はページ内検索で見つかるよう `until-found` にする） */
function showTabAt(container, index) {
    tabsOf(container).forEach((tab, i) => {
        const selected = i === index;
        const panel = document.getElementById(tab.getAttribute("aria-controls"));
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected)
            panel.removeAttribute("hidden");
        else
            panel.setAttribute("hidden", "until-found");
    });
}
/** タブを選び、group を持てば同じページの同じ group の並びを同じタブ名へ揃える（`save` が `true` のときは選んだタブ名を残す） */
function selectTab({ tab, save }) {
    const container = tab.closest(".doc-tabs");
    showTabAt(container, tabsOf(container).indexOf(tab));
    const group = container.dataset.group;
    if (!group)
        return;
    document.querySelectorAll(`.doc-tabs[data-group="${CSS.escape(group)}"]`).forEach((other) => {
        if (other === container)
            return;
        // そのタブ名が無い並びは変えない
        const index = tabsOf(other).findIndex((candidate) => candidate.dataset.name === tab.dataset.name);
        if (index >= 0)
            showTabAt(other, index);
    });
    if (save)
        saveTabChoice({ group, name: tab.dataset.name });
}
/** group ごとに選んだタブ名をブラウザの保存領域へ残す（使えないときは残さず、切り替えは続ける） */
function saveTabChoice({ group, name }) {
    try {
        localStorage.setItem(`${TAB_STORAGE_PREFIX}${group}`, name);
    }
    catch (e) {
        console.warn("タブの選択を保存できません", group, e);
    }
}
/** group で残した選んだタブ名を返す（残していないか、保存領域が使えないときは null） */
function loadTabChoice(group) {
    try {
        return localStorage.getItem(`${TAB_STORAGE_PREFIX}${group}`);
    }
    catch (e) {
        console.warn("タブの選択を読めません", group, e);
        return null;
    }
}
/** 要素がタブかタブの中身の中にあれば、外側まで包むタブを選ぶ（残さない） */
function selectTabOf(target) {
    if (target.matches(".doc-tab"))
        selectTab({ tab: target, save: false });
    for (let panel = target.closest(".doc-tabpanel"); panel; panel = panel.parentElement?.closest(".doc-tabpanel") ?? null) {
        selectTab({ tab: document.getElementById(panel.getAttribute("aria-labelledby")), save: false });
    }
}
/** タブ名の見出しを、識別子と # のリンクを付けずに見た目だけ隠してタブの中身の先頭へ戻す（目次と節の開閉を組み立てた後に呼ぶ） */
function restoreTabHeadings(article) {
    article.querySelectorAll(".doc-tab[data-level]").forEach((tab) => {
        const heading = tableEl(tab.dataset.level, { class: "visually-hidden doc-tab-heading", text: tab.dataset.name });
        document.getElementById(tab.getAttribute("aria-controls")).prepend(heading);
    });
}
/** 範囲 1 つの番号付きリストをステップにする */
function buildSteps(range) {
    const setup = resolveDocPartSetup({ range, part: "steps" });
    const warnings = [...setup.warnings];
    const lists = range.nodes.filter((node) => node instanceof HTMLOListElement);
    if (lists.length === 0)
        warnings.push(DOC_PART_LABELS.noOrderedList);
    lists.forEach((list) => {
        list.classList.add("doc-steps");
        // 番号と縦線は CSS が描く。`start` を持つリストは、その番号から数える
        list.style.setProperty("--steps-start", String(list.start - 1));
    });
    const count = lists.reduce((sum, list) => sum + list.querySelectorAll(":scope > li").length, 0);
    finishDocPart({ range, setup, warnings, warnTitle: DOC_PART_LABELS.stepsWarnTitle, foldSummary: formatLabel(DOC_PART_LABELS.stepsFold, { n: count }) });
}
/** コードブロックの言語指定を返す（`code` 自身か、rouge が `pre.highlight` を包む外枠のどちらかに付いている） */
function codeLanguageOf(pre) {
    const holder = pre.classList.contains("highlight") ? pre.closest(".highlighter-rouge") : pre.querySelector(":scope > code");
    return /language-([^\s]+)/.exec(holder?.className ?? "")?.[1] ?? "";
}
/** コードブロックを本文の中で置き換えるときの外側の要素を返す（rouge は外枠ごと） */
function codeBlockOuter(pre) {
    return pre.closest(".highlighter-rouge") ?? pre;
}
/** 言語指定 `tree` のコードブロックを、アイコン付きの入れ子のツリーに置き換える */
function buildFileTrees(article) {
    article.querySelectorAll("pre").forEach((pre) => {
        if (codeLanguageOf(pre) !== FILE_TREE_LANG)
            return;
        const text = (pre.querySelector("code") ?? pre).textContent.replace(/\n+$/, "");
        const { rows, warnings } = parseFileTree(text);
        const outer = codeBlockOuter(pre);
        // 読めない行があれば、ツリーにせず元のコードブロックの上に警告を置く
        if (warnings.length) {
            outer.before(buildTableWarning(DOC_PART_LABELS.treeWarnTitle, warnings));
            return;
        }
        const tree = tableEl("div", { class: "file-tree", role: "group", "aria-label": DOC_PART_LABELS.treeName }, [renderFileTree(rows)]);
        // コピーボタンは元の罫線のテキストを写す
        codeActions(tree).appendChild(createCopyButton(() => text));
        outer.replaceWith(tree);
    });
}
/** 罫線のテキストを、段・名前・注釈の並びに読む（読めない行は警告にし、行番号は 1 行目を 1 と数える） */
function parseFileTree(text) {
    const rows = [];
    const warnings = [];
    text.replace(/\n+$/, "").split("\n").forEach((raw, index) => {
        const line = index + 1;
        let rest = raw;
        let depth = 0;
        // 罫線の段を数え、項目の頭の罫線があれば 1 段深くする
        while (FILE_TREE_PATTERNS.indent.test(rest)) {
            rest = rest.replace(FILE_TREE_PATTERNS.indent, "");
            depth += 1;
        }
        if (FILE_TREE_PATTERNS.branch.test(rest)) {
            rest = rest.replace(FILE_TREE_PATTERNS.branch, "");
            depth += 1;
        }
        else if (depth > 0) {
            warnings.push(formatLabel(DOC_PART_LABELS.treeNoBranch, { line }));
            return;
        }
        // 上の行より 2 段以上深い行は親を決められない（先頭の行は 1 段より深い行）
        const previous = rows.at(-1);
        if (previous ? depth > previous.depth + 1 : depth > 1) {
            warnings.push(formatLabel(DOC_PART_LABELS.treeTooDeep, { line }));
            return;
        }
        const noted = FILE_TREE_PATTERNS.note.exec(rest);
        const name = (noted ? noted[1] : rest).trim();
        rows.push({ depth, name, note: noted?.[2].trim() ?? "", folder: name.endsWith("/") });
    });
    return { rows, warnings };
}
/** 項目の並びから、アイコン付きの入れ子のリストを作る（名前と注釈は文字として入れる） */
function renderFileTree(rows) {
    const createList = () => tableEl("ul", { class: "file-tree-list", role: "list" });
    const root = createList();
    // 段ごとの、項目を足していくリスト
    const lists = [root];
    let lastItem = null;
    rows.forEach((row) => {
        const level = row.depth - rows[0].depth;
        // 1 段深い項目は、直前の項目の中に子のリストを作って入れる
        if (level >= lists.length) {
            const child = createList();
            lastItem.append(child);
            lists.push(child);
        }
        lists.length = level + 1;
        const label = tableEl("span", { class: "file-tree-label" }, [tableEl("span", { class: "file-tree-name", text: row.name })]);
        if (row.note)
            label.append(" ", tableEl("span", { class: "file-tree-note", text: row.note }));
        const icon = tableEl("span", { html: FILE_TREE_ICONS[row.folder ? "folder" : "file"] }).firstElementChild;
        const item = tableEl("li", { class: "file-tree-item" }, [tableEl("span", { class: "file-tree-row" }, [icon, label])]);
        lists[level].append(item);
        lastItem = item;
    });
    return root;
}
/** 行末の印を持つコードブロックを行に分け、足した行・消した行・強調を当てる（知らない印は行に残して警告を置く） */
function buildCodeMarks(article) {
    article.querySelectorAll("pre").forEach((pre) => {
        const code = pre.querySelector(":scope > code");
        if (!code || CODE_MARK_SKIP_LANGS.includes(codeLanguageOf(pre)))
            return;
        const source = code.textContent;
        if (!source.includes(CODE_MARK_HEAD) && source.search(CODE_MARK_PATTERNS.escaped) < 0)
            return;
        const warnings = [];
        const copyLines = [];
        const lines = splitCodeLines(code.innerHTML).map((html, index) => {
            const line = tableEl("span", { class: "code-line", html });
            let mark = null;
            if (line.textContent.search(CODE_MARK_PATTERNS.escaped) >= 0) {
                // 打ち消した印は当てず、`\` を外した文字列にする
                const nodes = codeTextNodes(line);
                deleteLineChars(nodes, [...lineText(nodes).matchAll(CODE_MARK_PATTERNS.escaped)].map((match) => match.index + 1));
            }
            else {
                const name = CODE_MARK_PATTERNS.mark.exec(line.textContent)?.[1];
                if (name !== undefined && Object.hasOwn(CODE_LINE_MARKS, name)) {
                    mark = CODE_LINE_MARKS[name];
                    stripLineMark(line);
                }
                else if (name !== undefined) {
                    // 知らない印は当てずに残す
                    warnings.push(formatLabel(DOC_PART_LABELS.unknownMark, { line: index + 1, name, choices: Object.keys(CODE_LINE_MARKS).join("・") }));
                }
            }
            // 写す中身は記号と読み上げの文言を入れる前の文字から作る。消した行は含めない
            if (mark?.kind !== "del")
                copyLines.push(line.textContent);
            if (mark)
                line.classList.add(`code-line-${mark.kind}`);
            // 記号は読み上げから外し、足した行・消した行には読み上げにだけ届く文言を置く
            line.prepend(tableEl("span", { class: "code-line-sign", "aria-hidden": "true", text: mark?.sign ?? "" }));
            if (mark?.spoken)
                line.children[0].after(tableEl("span", { class: "visually-hidden", text: mark.spoken }));
            return line;
        });
        code.replaceChildren(...lines);
        code.dataset.copyText = copyLines.join("\n");
        pre.classList.add("has-code-marks");
        if (warnings.length)
            codeBlockOuter(pre).before(buildTableWarning(DOC_PART_LABELS.marksWarnTitle, warnings));
    });
}
/** 構文ハイライトの要素が行をまたぐときも、行ごとに閉じ直して包んだ HTML の並びを返す（末尾の空の行は含めない） */
function splitCodeLines(html) {
    const lines = [""];
    // 開いている要素の開きタグ
    const open = [];
    html.replace(/(<[^>]+>)|([^<]+)/g, (_match, tag, text) => {
        if (tag) {
            if (tag.startsWith("</"))
                open.pop();
            else
                open.push(tag);
            lines[lines.length - 1] += tag;
            return "";
        }
        // 文字の中の改行で、開いている要素を閉じて行を終え、次の行を同じ開きタグで始める
        text.split("\n").forEach((part, i) => {
            if (i > 0) {
                lines[lines.length - 1] += "</span>".repeat(open.length);
                lines.push(open.join(""));
            }
            lines[lines.length - 1] += part;
        });
        return "";
    });
    if (lines.length > 1 && lines[lines.length - 1].replace(/<[^>]+>/g, "") === "")
        lines.pop();
    return lines;
}
/** 要素の中の文字のノードを並びで返す */
function codeTextNodes(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode())
        nodes.push(walker.currentNode);
    return nodes;
}
/** 行の文字を、ノードをまたいだ 1 つの文字列にして返す（構文の色の要素が印を分けても、位置は文字列の上で決める） */
function lineText(nodes) {
    return nodes.map((node) => node.data).join("");
}
/** 行の文字の頭から keep 文字だけを残し、後ろをノードをまたいで外す */
function keepLineChars(nodes, keep) {
    let offset = 0;
    nodes.forEach((node) => {
        const length = node.data.length;
        node.data = node.data.slice(0, Math.max(0, keep - offset));
        offset += length;
    });
}
/** 行の文字の指定した位置の文字を、ノードをまたいで取り除く */
function deleteLineChars(nodes, positions) {
    let offset = 0;
    nodes.forEach((node) => {
        const length = node.data.length;
        node.data = node.data.split("").filter((_char, i) => !positions.includes(offset + i)).join("");
        offset += length;
    });
}
/** 行から、行末の印と、印だけを持っていた行コメントの頭と、その前の空白を外す（印の前に文字のある行コメントは残す） */
function stripLineMark(line) {
    const nodes = codeTextNodes(line);
    const text = lineText(nodes);
    // 印より前の文字から、末尾の空白と 1 つ目の行コメントの頭を外した長さだけを残す
    const beforeMark = text.slice(0, text.lastIndexOf(CODE_MARK_HEAD)).replace(/\s+$/, "");
    keepLineChars(nodes, beforeMark.replace(CODE_MARK_PATTERNS.commentLeader, "").replace(/\s+$/, "").length);
}
/** 頭が `badge` と `:` のインラインコードを、頭を外した文言のバッジに置き換える（打ち消しの `\` は外してインラインコードのまま残す） */
function buildBadges(article) {
    article.querySelectorAll("code").forEach((code) => {
        if (code.closest("pre"))
            return;
        const text = code.textContent;
        if (text.startsWith(BADGE_PREFIXES.escaped)) {
            code.textContent = BADGE_PREFIXES.badge + text.slice(BADGE_PREFIXES.escaped.length);
            return;
        }
        if (!text.startsWith(BADGE_PREFIXES.badge))
            return;
        const label = text.slice(BADGE_PREFIXES.badge.length).trim();
        // 頭の後ろが空白だけならバッジにしない
        if (label)
            code.replaceWith(tableEl("span", { class: "doc-badge", text: label }));
    });
}
async function init() {
    ensureToastElement();
    // 1. テーマを先に決める（フラッシュ抑止）
    bindThemeToggle();
    // 2. 共通レイアウトを組み立てる
    buildBreadcrumb();
    const article = document.querySelector(".markdown-body");
    const docsLayout = document.querySelector(".docs-layout");
    const sidebarSource = document.querySelector("[data-sidebar-source]");
    const nav = renderSidebar(sidebarSource, document.body.dataset.tab, document.body.dataset.page);
    const drawerToggle = document.querySelector("[data-drawer-toggle]");
    if (nav && docsLayout) {
        docsLayout.prepend(nav);
        layout.nav = nav;
        drawerToggle?.addEventListener("click", () => openDrawer(nav));
    }
    else {
        docsLayout?.classList.add("no-sidebar");
        if (drawerToggle)
            drawerToggle.hidden = true;
    }
    bindBackToTop();
    // 3. 本文へ後処理を掛ける
    if (article) {
        markCallouts(article);
        // 行の詳細の組み替えは、小さな表を包み・並べ替え・絞り込み・ピン留め・見出し行の追従から外すため、表の包みより前
        buildRowDetails(article);
        wrapTables(article);
        // 表の種類と機能は、表の横スクロールの後・見出しの開閉と列のメニューの紐付けより前
        enhanceTables(article);
    }
    else {
        // 本文を持たないページ（モックの実画面）は、document.body を本文として表の横スクロールと表の機能付けだけを掛ける
        wrapTables(document.body);
        enhanceTables(document.body);
    }
    insertHeadingAnchors(); // まず見出しに id を振る（TOC がそれを使う）
    // 本文のタブとステップは、見出しの識別子を受け取った後（タブ名の見出しはタブへ識別子を渡して本文から外れる）・見出しの開閉と目次より前
    if (article)
        enhanceDocParts(article);
    addCodeCopyButtons();
    addCodeLangLabels();
    // 見出しアンカーを付けた後、目次を作る前に、見出しを節の開閉ボタンにする
    if (article)
        enableSectionToggles(article);
    // 4. 見出しが確定してから目次を置く
    buildToc();
    // 目次に載せない・節の開閉にしないタブ名の見出しは、目次を置いた後にタブの中身へ戻す
    if (article)
        restoreTabHeadings(article);
    // 開発ドキュメントサーバーの差分のマーク・変更の量・元の行を見た目へ移し、表示する列・表の件数・Schema のタブ・項目の要点パネル・コメントを紐付ける
    // （差分のマークの付け替えは節の変更の量とコメントより先。対象の要素を持たないページではどれも何もしない）
    if (article) {
        applyDiffMarks(article);
        applySectionChanges(article);
        applySidebarChanges();
        bindColumnMenus(article);
        // すべて開くは、表示する列のボタンの隣に置くため列のメニューの紐付けの後
        bindExpandAll(article);
        bindLargeValues(article);
        bindTableCounts(article);
        bindSchemaTabs(article);
        bindItemPanel(article);
        bindComments(article);
    }
    bindRefBar();
    keepDiffOnLinks();
    // 5. markdown のコードブロックの中身を描く（描いた見出しを目次に載せず、描いた中の Mermaid も図にするため、目次の後・図の前）
    if (article)
        renderMarkdownBlocks(article);
    // 6. 検索と起票の入口を紐付ける
    bindSearchEntries();
    bindIssueEntries();
    // 7. 幅に応じてナビゲーションの配置を決め、以降の幅の変化にも追随させる
    applyWidth();
    mobileQuery.addEventListener("change", applyWidth);
    tocInlineQuery.addEventListener("change", applyWidth);
    // 8. モックのページであればデモの操作を紐付ける
    bindSearchFilter();
    bindRowClick();
    bindNewButton();
    bindEditMode();
    // 9. 別ページの見出しの図をリンクの位置へ置く（置いた図も描くため、図を描く前。元のページの応答待ちが、ここまでの処理を止めないよう最後の方に置く）
    if (article)
        await embedDiagrams(article);
    // 10. 埋め込みで加わったコードへコピーのボタンを付ける（付け終えたコードは飛ばす）
    addCodeCopyButtons();
    // 11. 図を描く
    if (article)
        await renderMermaid(article);
    // 12. 描いた図のうち変わった図に変更のマークを付ける
    if (article)
        markDiagramChanges(article);
}
document.addEventListener("DOMContentLoaded", init);
