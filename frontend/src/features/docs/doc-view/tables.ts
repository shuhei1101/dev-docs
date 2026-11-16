/** 表の直前に配置する表のマーカー（`<!-- table: ... -->`。複数行を含む） */
const TABLE_MARKER = /^<!--\s*table:([\s\S]*?)-->$/;
/** 複数行にわたる表のマーカーの始まりの行（`-->` を持たない） */
const TABLE_MARKER_OPEN = /^<!--\s*table:/;
/** コードブロックの始まりと終わり（```・~~~） */
const FENCE = /^\s{0,3}(`{3,}|~{3,})/;
/** 表の区切りの行（`---` の並び） */
const SEPARATOR_ROW = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

export type TableBlock = {
  key: string;
  /** 表の直前の表のマーカーの範囲（開始と終了の行。0 始まり）と文字列。無ければ null */
  marker: { start: number; end: number; text: string } | null;
  /** 列の表示・非表示の機能を持つ表か */
  columns: boolean;
};

/** JSON の記載の表のマーカーの引数のうち、列の表示・非表示に関わるもの */
type MarkerArgs = {
  features?: Record<string, { enabled?: boolean } & Record<string, unknown>>;
  columns?: Record<string, { hidden?: boolean } & Record<string, unknown>>;
} & Record<string, unknown>;

type TableSource = { markdown: string; tableKeys: string[] };

type Scan = {
  fence: string | null;
  inTable: boolean;
  /** 空行でない最後のまとまり（次の表の直前のマーカーの候補） */
  lastText: { start: number; end: number; text: string } | null;
  /** 読みかけの複数行の表のマーカー */
  open: { start: number; text: string } | null;
};

/** コードブロックの始まり・中・終わりの行なら状態を進めて true を返却する */
const scanFence = (scan: Scan, line: string): boolean => {
  const opened = FENCE.exec(line);
  if (scan.fence !== null) {
    if (
      opened &&
      opened[1][0] === scan.fence[0] &&
      opened[1].length >= scan.fence.length
    )
      scan.fence = null;
    return true;
  }
  if (!opened) return false;
  scan.fence = opened[1];
  scan.inTable = false;
  scan.lastText = null;
  scan.open = null;
  return true;
};

/** 複数行の表のマーカーの始まり・中・終わりの行なら状態を進めて true を返却する */
const scanMarker = (scan: Scan, line: string, index: number): boolean => {
  const text = line.trim();
  if (scan.open !== null) {
    scan.open.text = `${scan.open.text}\n${text}`;
    if (text.includes("-->")) {
      scan.lastText = { start: scan.open.start, end: index, text: scan.open.text };
      scan.open = null;
    }
    return true;
  }
  if (!TABLE_MARKER_OPEN.test(text) || text.includes("-->")) return false;
  scan.open = { start: index, text };
  scan.inTable = false;
  return true;
};

/** 表のマーカーの名前の後ろの引数を返却する */
const markerArgsText = (text: string): string =>
  (TABLE_MARKER.exec(text)?.[1] ?? "").trim();

/** JSON の記載の表のマーカーの引数を返却する。JSON の記載でないか読めなければ null */
const parseMarkerArgs = (text: string): MarkerArgs | null => {
  const args = markerArgsText(text);
  if (!args.startsWith("{")) return null;
  try {
    const parsed: unknown = JSON.parse(args);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as MarkerArgs)
      : null;
  } catch {
    return null;
  }
};

/** 表のマーカーが列の表示・非表示の機能を持つか */
const hasColumnsFeature = (text: string): boolean => {
  if (!markerArgsText(text).startsWith("{")) return text.includes("+columns");
  const args = parseMarkerArgs(text);
  if (args === null) return false;
  const feature = args.features?.columns;
  if (feature?.enabled === false) return false;
  return (
    feature !== undefined ||
    Object.values(args.columns ?? {}).some((column) => column.hidden === true)
  );
};

/** 表の直前の行が表のマーカーなら、その行を返却する */
const markerOf = (scan: Scan): TableBlock["marker"] =>
  scan.lastText !== null && TABLE_MARKER.test(scan.lastText.text)
    ? scan.lastText
    : null;

/** Markdown の表を出る順に表のキーと対にし、直前の表のマーカーと `+columns` の有無を返却する */
export const findTables = ({
  markdown,
  tableKeys,
}: TableSource): TableBlock[] => {
  const lines = markdown.split("\n");
  const tables: TableBlock[] = [];
  const scan: Scan = { fence: null, inTable: false, lastText: null, open: null };
  lines.forEach((line, index) => {
    // コードブロックの中は表として数えない
    if (scanFence(scan, line)) return;
    if (scanMarker(scan, line, index)) return;
    const isRow = line.trimStart().startsWith("|");
    if (isRow && !scan.inTable && SEPARATOR_ROW.test(lines[index + 1] ?? "")) {
      // 表の始まり: サーバーの表のキーと同じ数え方で、同じ番号のキーと対にする
      const key = tableKeys[tables.length];
      const marker = markerOf(scan);
      if (key !== undefined)
        tables.push({
          key,
          marker,
          columns: marker !== null && hasColumnsFeature(marker.text),
        });
      scan.inTable = true;
      return;
    }
    if (isRow) return;
    scan.inTable = false;
    if (line.trim()) scan.lastText = { start: index, end: index, text: line.trim() };
  });
  return tables;
};

/** JSON の記載の表のマーカーの全ての列の隠す設定を、保存した隠す列と一致させた引数を返却する */
const replaceHidden = (args: MarkerArgs, hidden: string[]): MarkerArgs => {
  const columns: NonNullable<MarkerArgs["columns"]> = {};
  for (const [name, setting] of Object.entries(args.columns ?? {})) {
    const { hidden: _, ...rest } = setting;
    if (Object.keys(rest).length > 0) columns[name] = rest;
  }
  for (const name of hidden) columns[name] = { ...columns[name], hidden: true };
  const { columns: __, ...result } = args;
  if (Object.keys(columns).length > 0) result.columns = columns;
  // 隠す列が無くなっても、列の表示・非表示の機能を残す（mdmark の tableIndex をずらさない）
  if (hidden.length === 0)
    result.features = { ...args.features, columns: args.features?.columns ?? {} };
  return result;
};

/** 保存した隠す列を、列の表示・非表示の機能を持つ表のマーカーへ書き込む */
export const applyHiddenColumns = ({
  markdown,
  tableKeys,
  columns,
}: TableSource & { columns: Record<string, string[]> }): string => {
  const lines = markdown.split("\n");
  // 複数行のマーカーを 1 行に置き換えても前の表の行がずれないよう、後ろの表から書き込む
  for (const table of findTables({ markdown, tableKeys }).reverse()) {
    const hidden = columns[table.key];
    if (!table.columns || table.marker === null || hidden === undefined) continue;
    const { start, end, text } = table.marker;
    const args = parseMarkerArgs(text);
    if (args !== null) {
      const replaced = `<!-- table: ${JSON.stringify(replaceHidden(args, hidden))} -->`;
      lines.splice(start, end - start + 1, replaced);
    } else if (hidden.length > 0) {
      lines[start] = lines[start].replace(/\s*-->\s*$/, ` hide=${hidden.join(",")} -->`);
    }
  }
  return lines.join("\n");
};

/** 列の表示・非表示の機能を持つ表のキーだけを出る順に並べる（mdmark の `tableIndex` の番号に対応する） */
export const columnTableKeys = (source: TableSource): string[] =>
  findTables(source)
    .filter((table) => table.columns)
    .map((table) => table.key);
