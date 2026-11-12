/** 表の直前に配置する表のマーカー（`<!-- table: ... -->`） */
const TABLE_MARKER = /^<!--\s*table:[^>]*-->\s*$/;
/** コードブロックの始まりと終わり（```・~~~） */
const FENCE = /^\s{0,3}(`{3,}|~{3,})/;
/** 表の区切りの行（`---` の並び） */
const SEPARATOR_ROW = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

export type TableBlock = {
  key: string;
  /** 表の直前の表のマーカーの行（0 始まり）と文字列。無ければ null */
  marker: { line: number; text: string } | null;
  /** マーカーが `+columns` を持つか */
  columns: boolean;
};

type TableSource = { markdown: string; tableKeys: string[] };

type Scan = {
  fence: string | null;
  inTable: boolean;
  /** 空行でない最後の行（次の表の直前の行の候補） */
  lastText: { line: number; text: string } | null;
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
  return true;
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
  const scan: Scan = { fence: null, inTable: false, lastText: null };
  lines.forEach((line, index) => {
    // コードブロックの中は表として数えない
    if (scanFence(scan, line)) return;
    const isRow = line.trimStart().startsWith("|");
    if (isRow && !scan.inTable && SEPARATOR_ROW.test(lines[index + 1] ?? "")) {
      // 表の始まり: サーバーの表のキーと同じ数え方で、同じ番号のキーと対にする
      const key = tableKeys[tables.length];
      const marker = markerOf(scan);
      if (key !== undefined)
        tables.push({
          key,
          marker,
          columns: marker?.text.includes("+columns") ?? false,
        });
      scan.inTable = true;
      return;
    }
    if (isRow) return;
    scan.inTable = false;
    if (line.trim()) scan.lastText = { line: index, text: line.trim() };
  });
  return tables;
};

/** 隠す列を、その表のマーカー（`+columns` の表）へ `hide=` で書き込む */
export const applyHiddenColumns = ({
  markdown,
  tableKeys,
  columns,
}: TableSource & { columns: Record<string, string[]> }): string => {
  const lines = markdown.split("\n");
  for (const table of findTables({ markdown, tableKeys })) {
    const hidden = columns[table.key];
    if (!table.columns || table.marker === null || !hidden?.length) continue;
    lines[table.marker.line] = lines[table.marker.line].replace(
      /\s*-->\s*$/,
      ` hide=${hidden.join(",")} -->`,
    );
  }
  return lines.join("\n");
};

/** `+columns` の表のキーだけを出る順に並べる（mdmark の `tableIndex` の番号に対応する） */
export const columnTableKeys = (source: TableSource): string[] =>
  findTables(source)
    .filter((table) => table.columns)
    .map((table) => table.key);
