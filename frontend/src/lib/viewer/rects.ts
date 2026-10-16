import type { Rect } from "../api";

/** Union the selection's rects that sit on the same text line (one highlight rect per line). */
export function mergeLines(rects: Rect[]): Rect[] {
  const lines: Rect[] = [];
  for (const r of [...rects].sort((a, b) => a[1] - b[1] || a[0] - b[0])) {
    const last = lines[lines.length - 1];
    const overlap = last ? Math.min(last[3], r[3]) - Math.max(last[1], r[1]) : 0;
    if (last && overlap > 0.5 * Math.min(last[3] - last[1], r[3] - r[1])) {
      lines[lines.length - 1] = [Math.min(last[0], r[0]), Math.min(last[1], r[1]), Math.max(last[2], r[2]), Math.max(last[3], r[3])];
    } else lines.push(r);
  }
  return lines;
}
