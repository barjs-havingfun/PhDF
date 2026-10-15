// Markdown → HTML for the preview. HTML in the source is escaped (html: false); pin lines become
// clickable cards.
import MarkdownIt from "markdown-it";
import { parsePin, PIN_MARK } from "../pin";

const md = new MarkdownIt({ html: false, linkify: true, breaks: false });

const escape = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export function renderMarkdown(text: string): string {
  const cards: string[] = [];
  // Replace pin lines by placeholders that survive Markdown rendering, then swap the cards in.
  const source = text
    .split("\n")
    .map((line) => {
      const pin = line.startsWith(PIN_MARK) ? parsePin(line) : null;
      if (!pin) return line;
      const label = `p.${pin.page + 1}${pin.section ? ` · §${pin.section}` : ""}`;
      cards.push(
        `<button class="pin-card" data-pin-id="${escape(pin.id)}" data-pin-page="${pin.page}">` +
          `${PIN_MARK} ${escape(label)} <span class="pin-go">· Go to PDF ↗</span></button>`,
      );
      return `\n\nPHDFPIN${cards.length - 1}\n`;
    })
    .join("\n");
  return md.render(source).replace(/<p>PHDFPIN(\d+)<\/p>/g, (_, i) => cards[Number(i)]);
}
