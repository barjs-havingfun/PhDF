// PhDF pins: the anchor lines that tie a Markdown note to a place in a PDF.
//
//   ⎘ phdf · p.12 · §2.1 · #k7q2
//   > “The dominant sequence transduction models are based on …”
//
//   your own notes…
//
// The id is the PDF annotation's /NM id, so the pin finds the exact highlight; the page (and the
// quote) are a readable fallback when the annotation is gone.

import type { Annotation, OutlineItem } from "./api";

export const PIN_MARK = "⎘";
export const PIN_RE = /^⎘ phdf · p\.(\d+)(?: · §(.+?))? · #([a-z0-9]{3,12})\s*$/;

export interface Pin {
  page: number; // 0-based
  section: string | null;
  id: string;
  line: number; // 1-based line in the Markdown text
}

export function parsePin(line: string, lineNo = 0): Pin | null {
  const m = PIN_RE.exec(line);
  return m ? { page: Number(m[1]) - 1, section: m[2] ?? null, id: m[3], line: lineNo } : null;
}

export function findPins(text: string): Pin[] {
  const pins: Pin[] = [];
  text.split("\n").forEach((line, i) => {
    if (line.startsWith(PIN_MARK)) {
      const pin = parsePin(line, i + 1);
      if (pin) pins.push(pin);
    }
  });
  return pins;
}

export function formatPin(page: number, id: string, section: string | null): string {
  return `${PIN_MARK} phdf · p.${page + 1}${section ? ` · §${section}` : ""} · #${id}`;
}

const MAX_QUOTE = 600;

/** The block inserted into the note for an annotation; ends with an empty line to write on. */
export function pinBlock(annot: Annotation, section: string | null): string {
  let quote = annot.quote.trim();
  if (quote.length > MAX_QUOTE) quote = quote.slice(0, MAX_QUOTE).trimEnd() + "…";
  const lines = [formatPin(annot.page, annot.id, section)];
  if (quote) lines.push(`> “${quote}”`);
  return lines.join("\n") + "\n\n";
}

/** Short section label for a page from the outline: "2.1" for numbered headings, else a title. */
export function sectionFor(outline: OutlineItem[] | null, page: number): string | null {
  if (!outline) return null;
  let best: OutlineItem | null = null;
  const walk = (items: OutlineItem[]) => {
    for (const item of items) {
      if (item.page >= 0 && item.page <= page && (!best || item.page >= best.page)) best = item;
      walk(item.children);
    }
  };
  walk(outline);
  if (!best) return null;
  const title = (best as OutlineItem).title.trim().replace(/[·#\n]/g, " ");
  const numbered = /^(\d+(?:\.\d+)*)\b/.exec(title);
  if (numbered) return numbered[1];
  return title.length > 28 ? title.slice(0, 27).trimEnd() + "…" : title;
}
