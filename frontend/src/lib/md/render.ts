// Markdown → HTML for the preview. HTML in the source is escaped (html: false); pin lines become
// clickable cards and $…$ / $$…$$ math is typeset with KaTeX.
import katex from "katex";
import "katex/dist/katex.min.css";
import MarkdownIt from "markdown-it";
import { parsePin, PIN_MARK } from "../pin";

const md = new MarkdownIt({ html: false, linkify: true, breaks: false });

const escape = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const tex = (src: string, display: boolean) =>
  katex.renderToString(src, { displayMode: display, throwOnError: false, output: "html" });

/** Typeset math outside code: $$…$$ blocks (may span lines) and $…$ inline (not "$5 and $6"). */
function withMath(text: string, slots: string[]): string {
  const slot = (html: string, block: boolean) => {
    slots.push(html);
    return block ? `\n\nPHDFMATH${slots.length - 1}\n\n` : `PHDFMATH${slots.length - 1}`;
  };
  return text
    .split(/(^```[\s\S]*?^```|`[^`\n]*`)/m)
    .map((part, i) => {
      if (i % 2) return part; // code: leave alone
      return part
        .replace(/\$\$([\s\S]+?)\$\$/g, (_, src) => slot(tex(src.trim(), true), true))
        .replace(/(^|[^\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?!\d)/g, (_, pre, src) => pre + slot(tex(src, false), false));
    })
    .join("");
}

export function renderMarkdown(text: string): string {
  const math: string[] = [];
  text = withMath(text, math);
  const cards: string[] = [];
  // Replace pin lines by placeholders that survive Markdown rendering, then swap the cards in.
  const source = text
    .split("\n")
    .filter((line) => !/^<!-- \/?phdf:[\w-]+.*-->$/.test(line.trim())) // PhDF's section markers
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
  return md
    .render(source)
    .replace(/<p>PHDFPIN(\d+)<\/p>/g, (_, i) => cards[Number(i)])
    .replace(/<p>PHDFMATH(\d+)<\/p>/g, (_, i) => `<div class="math-block">${math[Number(i)]}</div>`)
    .replace(/PHDFMATH(\d+)/g, (_, i) => math[Number(i)]);
}
