// “Quote” — Title, p. 12 (copy with citation).
import type { Tab } from "./tab.svelte";

export function citation(tab: Tab, text: string, pages: number[]): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b).map((p) => p + 1);
  const where = !sorted.length ? "" : sorted.length > 1 ? `, pp. ${sorted[0]}–${sorted[sorted.length - 1]}` : `, p. ${sorted[0]}`;
  const quote = text.replace(/\s+/g, " ").trim();
  return `“${quote}” — ${tab.title}${where}`;
}
