// The grades table: a Markdown table in the folder's .grades.md, one row per exam,
// `| # | Name | Grade | Comment |`. The user may add columns or text around it; only the
// cells PhDF owns are touched and everything else is written back as it was.

export const COLUMNS = ["#", "Name", "Grade", "Comment"];

export interface Table {
  header: string[];
  rows: string[][];
  /** Line range of the table in the file: [start, end). */
  start: number;
  end: number;
}

function cells(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}

const isRow = (line: string) => line.trim().startsWith("|");
const isRule = (line: string) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);

/** The first table with "#", "Name" and "Grade" columns. */
export function parse(text: string): Table | null {
  const lines = text.split("\n");
  for (let i = 0; i + 1 < lines.length; i++) {
    if (!isRow(lines[i]) || !isRule(lines[i + 1])) continue;
    const header = cells(lines[i]);
    const lower = header.map((h) => h.toLowerCase());
    if (!lower.includes("#") || !lower.includes("name") || !lower.includes("grade")) continue;
    let end = i + 2;
    const rows: string[][] = [];
    while (end < lines.length && isRow(lines[end])) {
      const row = cells(lines[end]);
      while (row.length < header.length) row.push("");
      rows.push(row.slice(0, header.length));
      end++;
    }
    return { header, rows, start: i, end };
  }
  return null;
}

const escapeCell = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");

function render(t: Table): string[] {
  const all = [t.header, ...t.rows].map((r) => r.map(escapeCell));
  const widths = t.header.map((_, c) => Math.max(3, ...all.map((r) => (r[c] ?? "").length)));
  const line = (r: string[]) => `| ${r.map((v, c) => (v ?? "").padEnd(widths[c])).join(" | ")} |`;
  return [line(all[0]), `|${widths.map((w) => "-".repeat(w + 2)).join("|")}|`, ...all.slice(1).map(line)];
}

function write(text: string, t: Table): string {
  const lines = text.split("\n");
  lines.splice(t.start, t.end - t.start, ...render(t));
  return lines.join("\n");
}

export function newTableText(title: string, count: number): string {
  const rows = Array.from({ length: count }, (_, i) => [String(i + 1), "", "", ""]);
  const t: Table = { header: [...COLUMNS], rows, start: 0, end: 0 };
  return `# Grades — ${title}\n\n${render(t).join("\n")}\n`;
}

/** Make sure there is a row for exams 1..count. Names start empty: PDF names are not copied
 *  in — the user (or the identification drawer) fills them. */
export function ensureRows(text: string, title: string, count: number): string {
  const t = parse(text);
  if (!t) {
    const table = newTableText(title, count);
    return text.trim() ? `${text.replace(/\s*$/, "")}\n\n${table.replace(/^# .*\n\n/, "")}` : table;
  }
  const num = col(t, "#");
  const have = new Set(t.rows.map((r) => r[num]));
  let changed = false;
  for (let i = 1; i <= count; i++) {
    if (have.has(String(i))) continue;
    const row = t.header.map(() => "");
    row[num] = String(i);
    t.rows.push(row);
    changed = true;
  }
  return changed ? write(text, t) : text;
}

function col(t: Table, name: string): number {
  return t.header.findIndex((h) => h.toLowerCase() === name.toLowerCase());
}

function rowOf(t: Table, num: number): string[] | undefined {
  const c = col(t, "#");
  return t.rows.find((r) => r[c] === String(num));
}

/** A cell of exam `num` ("Name", "Grade", …), or "" when there is none. */
export function getCell(text: string, num: number, column: string): string {
  const t = parse(text);
  if (!t) return "";
  const c = col(t, column);
  return c >= 0 ? (rowOf(t, num)?.[c] ?? "") : "";
}

/** Set cells of exam `num`; columns missing from the table are skipped. */
export function setCells(text: string, num: number, values: Record<string, string>): string {
  const t = parse(text);
  if (!t) return text;
  const row = rowOf(t, num);
  if (!row) return text;
  for (const [column, value] of Object.entries(values)) {
    const c = col(t, column);
    if (c >= 0) row[c] = value.trim();
  }
  return write(text, t);
}

/** The table as CSV (every column, including the user's own). */
export function toCsv(text: string): string {
  const t = parse(text);
  if (!t) return "";
  const field = (v: string) => (/[",;\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [t.header, ...t.rows].map((r) => r.map(field).join(",")).join("\r\n") + "\r\n";
}
