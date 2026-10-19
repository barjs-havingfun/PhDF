import type { Rect } from "../api";
import type { TextSelection } from "./Viewer.svelte";

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

/** Ctrl / ⌘-drag parts as one selection: texts in reading order with a blank line between
 *  them, rects merged per page, and each part's rects kept apart (`parts`, one highlight
 *  each). `box` places the menu. */
export function joinParts(all: TextSelection[], box: DOMRect): TextSelection | null {
  if (!all.length) return null;
  if (all.length === 1) return { ...all[0], box };
  const start = (s: TextSelection) => {
    const page = Math.min(...s.byPage.keys());
    return page * 1e6 + s.byPage.get(page)![0][1];
  };
  const sorted = [...all].sort((a, b) => start(a) - start(b));
  const byPage = new Map<number, Rect[]>();
  for (const s of sorted) for (const [page, rects] of s.byPage) byPage.set(page, [...(byPage.get(page) ?? []), ...rects]);
  return {
    text: sorted.map((s) => s.text.trim()).join("\n\n"),
    byPage,
    box,
    parts: sorted.map((s) => s.byPage),
  };
}
