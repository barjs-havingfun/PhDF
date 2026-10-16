// Markdown formatting commands for the note editor (format bar and right-click menu). They work
// on the CodeMirror selection: inline marks wrap / unwrap it, paragraph styles rewrite the
// prefixes of the selected lines, inserts put a template at the cursor.
import type { EditorView } from "@codemirror/view";

export type Inline = "bold" | "italic" | "strike" | "highlight" | "code" | "math" | "comment";
export type Block = "body" | "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "quote" | "bullet" | "numbered" | "task";
export type Insert = "footnote" | "table" | "callout" | "rule" | "codeblock" | "mathblock";

export const INLINE: Record<Inline, { mark: string; label: string; key?: string }> = {
  bold: { mark: "**", label: "Bold", key: "Ctrl+B" },
  italic: { mark: "*", label: "Italic", key: "Ctrl+I" },
  strike: { mark: "~~", label: "Strikethrough", key: "Ctrl+Shift+X" },
  highlight: { mark: "==", label: "Highlight", key: "Ctrl+Shift+H" },
  code: { mark: "`", label: "Code", key: "Ctrl+E" },
  math: { mark: "$", label: "Math" },
  comment: { mark: "%%", label: "Comment" },
};

export const BLOCKS: Record<Block, string> = {
  body: "Body",
  h1: "Heading 1",
  h2: "Heading 2",
  h3: "Heading 3",
  h4: "Heading 4",
  h5: "Heading 5",
  h6: "Heading 6",
  quote: "Quote",
  bullet: "Bullet List",
  numbered: "Numbered List",
  task: "Task List",
};

export const INSERTS: Record<Insert, string> = {
  footnote: "Footnote",
  table: "Table",
  callout: "Callout",
  rule: "Horizontal Rule",
  codeblock: "Code Block",
  mathblock: "Math Block",
};

const PREFIX = /^(#{1,6} |> |- \[[ xX]\] |[-*+] |\d+[.)] )/;

/** The paragraph style of a line. */
export function blockOf(line: string): Block {
  const m = line.match(PREFIX)?.[1] ?? "";
  if (m.startsWith("#")) return `h${m.length - 1}` as Block;
  if (m === "> ") return "quote";
  if (m.startsWith("- [")) return "task";
  if (/^[-*+] $/.test(m)) return "bullet";
  if (/^\d/.test(m)) return "numbered";
  return "body";
}

/** Wrap the selection in a mark, or remove it when it is already wrapped. */
export function toggleInline(view: EditorView, kind: Inline) {
  const mark = INLINE[kind].mark;
  const { state } = view;
  const { from, to } = state.selection.main;
  const n = mark.length;
  const before = state.sliceDoc(Math.max(0, from - n), from);
  const after = state.sliceDoc(to, to + n);
  if (before === mark && after === mark) {
    view.dispatch({
      changes: [{ from: from - n, to: from }, { from: to, to: to + n }],
      selection: { anchor: from - n, head: to - n },
    });
  } else {
    view.dispatch({
      changes: [{ from, insert: mark }, { from: to, insert: mark }],
      selection: { anchor: from + n, head: to + n },
    });
  }
  view.focus();
}

/** Plain text: inline marks, links, images and line prefixes removed. */
export function stripMarkdown(text: string): string {
  return text
    .split("\n")
    .map((line) => line.replace(PREFIX, ""))
    .join("\n")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/%%[\s\S]*?%%/g, "")
    .replace(/(\*\*|__|~~|==|\*|_|`|\$)(?=\S)([\s\S]*?\S)\1/g, "$2");
}

export function clearFormatting(view: EditorView) {
  const { from, to } = view.state.selection.main;
  const text = stripMarkdown(view.state.sliceDoc(from, to));
  view.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from, head: from + text.length } });
  view.focus();
}

/** [selection](url) with "url" selected to type over. */
export function insertLink(view: EditorView) {
  const { from, to } = view.state.selection.main;
  const label = view.state.sliceDoc(from, to) || "link";
  const text = `[${label}](url)`;
  const urlAt = from + label.length + 3;
  view.dispatch({ changes: { from, to, insert: text }, selection: { anchor: urlAt, head: urlAt + 3 } });
  view.focus();
}

/** Give every selected line a paragraph style (replacing the one it had). */
export function setBlock(view: EditorView, kind: Block) {
  const { state } = view;
  const { from, to } = state.selection.main;
  const first = state.doc.lineAt(from).number;
  const last = state.doc.lineAt(to).number;
  const changes = [];
  for (let n = first, i = 1; n <= last; n++, i++) {
    const line = state.doc.line(n);
    const old = line.text.match(PREFIX)?.[1] ?? "";
    const prefix =
      kind === "body" ? "" :
      kind.startsWith("h") ? "#".repeat(Number(kind[1])) + " " :
      kind === "quote" ? "> " : kind === "bullet" ? "- " : kind === "task" ? "- [ ] " : `${i}. `; // prettier-ignore
    changes.push({ from: line.from, to: line.from + old.length, insert: prefix });
  }
  view.dispatch({ changes });
  view.focus();
}

const TEMPLATES: Record<Exclude<Insert, "footnote">, { text: string; cursor: number }> = {
  table: { text: "| Column | Column |\n| ------ | ------ |\n|        |        |\n", cursor: 2 },
  callout: { text: "> [!note]\n> ", cursor: 12 },
  rule: { text: "---\n", cursor: 4 },
  codeblock: { text: "```\n\n```\n", cursor: 4 },
  mathblock: { text: "$$\n\n$$\n", cursor: 3 },
};

/** Insert a block on its own line at the cursor, or a footnote mark with its text at the end. */
export function insertBlock(view: EditorView, kind: Insert) {
  const { state } = view;
  const pos = state.selection.main.head;
  if (kind === "footnote") {
    const used = [...state.doc.toString().matchAll(/\[\^(\d+)\]/g)].map((m) => Number(m[1]));
    const n = Math.max(0, ...used) + 1;
    const end = state.doc.length;
    const tail = `${state.doc.toString().endsWith("\n") ? "\n" : "\n\n"}[^${n}]: `;
    view.dispatch({
      changes: [{ from: pos, insert: `[^${n}]` }, { from: end, insert: tail }],
      selection: { anchor: end + `[^${n}]`.length + tail.length },
      scrollIntoView: true,
    });
  } else {
    const line = state.doc.lineAt(pos);
    const { text, cursor } = TEMPLATES[kind];
    // Its own paragraph: after the current line when it has text.
    const at = line.text.trim() ? line.to : line.from;
    const head = line.text.trim() ? "\n\n" : "";
    view.dispatch({
      changes: { from: at, to: line.text.trim() ? at : line.to, insert: head + text },
      selection: { anchor: at + head.length + cursor },
      scrollIntoView: true,
    });
  }
  view.focus();
}

// --- clipboard -------------------------------------------------------------------------------------

export async function cut(view: EditorView) {
  const { from, to } = view.state.selection.main;
  if (from === to) return;
  await navigator.clipboard.writeText(view.state.sliceDoc(from, to));
  view.dispatch({ changes: { from, to } });
  view.focus();
}

export async function copy(view: EditorView) {
  const { from, to } = view.state.selection.main;
  if (from !== to) await navigator.clipboard.writeText(view.state.sliceDoc(from, to));
  view.focus();
}

/** Paste the clipboard's text; `plain` drops its Markdown formatting first. */
export async function paste(view: EditorView, plain = false) {
  let text = await navigator.clipboard.readText();
  if (plain) text = stripMarkdown(text);
  const { from, to } = view.state.selection.main;
  view.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length }, scrollIntoView: true });
  view.focus();
}
