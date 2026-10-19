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

/** `fn` applied to the text outside code (fenced blocks, inline spans); code stays as written. */
const outsideCode = (text: string, fn: (part: string) => string) =>
  text
    .split(/(^```[\s\S]*?^```|`[^`\n]*`)/m)
    .map((part, i) => (i % 2 ? part : fn(part)))
    .join("");

/** Typeset math outside code: $$…$$ blocks (may span lines) and $…$ inline (not "$5 and $6"). */
function withMath(text: string, slots: string[]): string {
  const slot = (html: string, block: boolean) => {
    slots.push(html);
    return block ? `\n\nPHDFMATH${slots.length - 1}\n\n` : `PHDFMATH${slots.length - 1}`;
  };
  return outsideCode(text, (part) =>
    part
      .replace(/%%[\s\S]*?%%/g, "") // Obsidian comments: not shown
      .replace(/==(?=\S)([^=\n]+?)(?<=\S)==/g, (_, s) => slot(`<mark>${escape(s)}</mark>`, false))
      .replace(/\$\$([\s\S]+?)\$\$/g, (_, src) => slot(tex(src.trim(), true), true))
      .replace(/(^|[^\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?!\d)/g, (_, pre, src) => pre + slot(tex(src, false), false)),
  );
}

const CALLOUT_ICONS: Record<string, string> = {
  note: "📝", info: "ℹ️", tip: "💡", success: "✅", question: "❓", warning: "⚠️",
  danger: "⛔", error: "⛔", example: "📋", quote: "❝", abstract: "📄", todo: "☑️",
}; // prettier-ignore

/** Footnotes: `[^1]` marks become superscripts, `[^1]: text` lines a list at the end. Code that
 *  shows this syntax is left alone. */
function withFootnotes(text: string, slots: string[], blocks: string[]): string {
  const notes: { id: string; body: string }[] = [];
  text = outsideCode(text, (part) => part.replace(/^\[\^([^\]\s]+)\]:[ \t]?(.*)$/gm, (_, id, body) => (notes.push({ id, body }), "")));
  if (!notes.length) return text;
  const ref = (m: string, id: string) => {
    const n = notes.findIndex((x) => x.id === id) + 1;
    if (!n) return m;
    slots.push(`<sup class="fn"><a href="#fn-${n}" id="fnref-${n}">${n}</a></sup>`);
    return `PHDFMATH${slots.length - 1}`;
  };
  text = outsideCode(text, (part) => part.replace(/\[\^([^\]\s]+)\]/g, ref));
  const items = notes.map((x, i) => `<li id="fn-${i + 1}">${md.renderInline(x.body)} <a href="#fnref-${i + 1}">↩</a></li>`);
  blocks.push(`<section class="footnotes"><ol>${items.join("")}</ol></section>`);
  return `${text}\n\nPHDFHTML${blocks.length - 1}\n`;
}

export function renderMarkdown(text: string): string {
  const math: string[] = [];
  const blocks: string[] = [];
  text = withFootnotes(text, math, blocks);
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
    .replace(/<p>PHDFHTML(\d+)<\/p>/g, (_, i) => blocks[Number(i)])
    .replace(/PHDFMATH(\d+)/g, (_, i) => math[Number(i)])
    // Task lists: - [ ] / - [x]
    .replace(/<li>(<p>)?\[( |x|X)\] /g, (_, p, c) => `<li class="task">${p ?? ""}<input type="checkbox" disabled${c === " " ? "" : " checked"}> `)
    // Callouts: > [!type] Title
    .replace(/<blockquote>\n<p>\[!(\w+)\][+-]?[ \t]?([^\n<]*)\n?/g, (_, type: string, title: string) => {
      const kind = type.toLowerCase();
      const label = title.trim() || kind[0].toUpperCase() + kind.slice(1);
      return `<blockquote class="callout callout-${escape(kind)}"><p class="callout-title">${CALLOUT_ICONS[kind] ?? "📌"} ${label}</p>\n<p>`;
    });
}
