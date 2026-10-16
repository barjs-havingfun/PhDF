// "Live" mode of the note editor (like Obsidian's live preview): Markdown marks are hidden and
// the text looks formatted, except on the lines being edited, which show the raw Markdown.
import { syntaxTree } from "@codemirror/language";
import { StateField, type EditorState, type Range } from "@codemirror/state";
import { Decoration, EditorView, ViewPlugin, WidgetType, type DecorationSet, type ViewUpdate } from "@codemirror/view";
import katex from "katex";

const hide = Decoration.replace({});
const markText = Decoration.mark({ class: "cm-live-mark" });
const commentText = Decoration.mark({ class: "cm-live-comment" });
const quoteLine = Decoration.line({ class: "cm-live-quote" });

class Bullet extends WidgetType {
  toDOM() {
    const el = document.createElement("span");
    el.className = "cm-live-bullet";
    el.textContent = "•";
    return el;
  }
}

class Rule extends WidgetType {
  toDOM() {
    const el = document.createElement("span");
    el.className = "cm-live-rule";
    return el;
  }
}

/** A task's [ ] / [x] as a checkbox; clicking it ticks the task in the text. */
class Checkbox extends WidgetType {
  constructor(
    readonly checked: boolean,
    readonly at: number,
  ) {
    super();
  }
  eq(other: Checkbox) {
    return other.checked === this.checked && other.at === this.at;
  }
  toDOM(view: EditorView) {
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "cm-live-task";
    box.checked = this.checked;
    box.onmousedown = (e) => {
      e.preventDefault();
      view.dispatch({ changes: { from: this.at + 1, to: this.at + 2, insert: this.checked ? " " : "x" } });
    };
    return box;
  }
  ignoreEvent() {
    return false;
  }
}

function build(view: EditorView): DecorationSet {
  const { state } = view;
  const active = new Set<number>(); // lines with the cursor or selection: shown raw
  for (const r of state.selection.ranges) {
    for (let n = state.doc.lineAt(r.from).number; n <= state.doc.lineAt(r.to).number; n++) active.add(n);
  }
  const isActive = (pos: number) => active.has(state.doc.lineAt(pos).number);
  const out: Range<Decoration>[] = [];

  for (const { from, to } of view.visibleRanges) {
    syntaxTree(state).iterate({
      from,
      to,
      enter: (node) => {
        const name = node.name;
        const parent = node.node.parent?.name ?? "";
        if (name === "Blockquote") {
          for (let p = node.from; p <= node.to; ) {
            const line = state.doc.lineAt(p);
            out.push(quoteLine.range(line.from));
            p = line.to + 1;
          }
        }
        if (isActive(node.from)) return;
        const next = state.sliceDoc(node.to, node.to + 1);
        if (name === "HeaderMark" || name === "QuoteMark") {
          out.push(hide.range(node.from, next === " " ? node.to + 1 : node.to));
        } else if (name === "EmphasisMark" || name === "StrikethroughMark") {
          out.push(hide.range(node.from, node.to));
        } else if (name === "CodeMark" && parent === "InlineCode") {
          out.push(hide.range(node.from, node.to));
        } else if ((name === "LinkMark" || name === "URL" || name === "LinkTitle") && parent === "Link") {
          out.push(hide.range(node.from, node.to));
        } else if (name === "ListMark" && node.node.parent?.parent?.name === "BulletList") {
          const task = state.sliceDoc(node.to, node.to + 4).match(/^ \[[ xX]\]/);
          if (!task) out.push(Decoration.replace({ widget: new Bullet() }).range(node.from, node.to));
          else out.push(hide.range(node.from, node.to + 1)); // "- " before a task box
        } else if (name === "TaskMarker") {
          const checked = /x/i.test(state.sliceDoc(node.from, node.to));
          out.push(Decoration.replace({ widget: new Checkbox(checked, node.from) }).range(node.from, node.to));
        } else if (name === "HorizontalRule") {
          out.push(Decoration.replace({ widget: new Rule() }).range(node.from, node.to));
        }
      },
    });

    // Obsidian extras the parser doesn't know: ==highlight== and %%comment%% (one line each).
    for (let pos = from; pos <= to; ) {
      const line = state.doc.lineAt(pos);
      const raw = isActive(line.from);
      for (const m of line.text.matchAll(/==(?=\S)([^=\n]+?)(?<=\S)==|%%[^%\n]*%%/g)) {
        const start = line.from + m.index!;
        const end = start + m[0].length;
        if (m[0].startsWith("%%")) {
          out.push(commentText.range(start, end));
          continue;
        }
        if (!raw) out.push(hide.range(start, start + 2), hide.range(end - 2, end));
        out.push(markText.range(start + 2, end - 2));
      }
      pos = line.to + 1;
    }
  }
  return Decoration.set(out, true);
}

const plugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = build(view);
    }
    update(u: ViewUpdate) {
      if (u.docChanged || u.viewportChanged || u.selectionSet) this.decorations = build(u.view);
    }
  },
  { decorations: (p) => p.decorations },
);

const look = EditorView.baseTheme({
  ".cm-live-mark": { background: "rgb(255 214 10 / 0.4)", borderRadius: "2px" },
  ".cm-live-comment": { color: "var(--tertiary)", fontStyle: "italic" },
  ".cm-live-quote": { borderLeft: "3px solid var(--separator)", paddingLeft: "12px !important", color: "var(--secondary)" },
  ".cm-live-bullet": { display: "inline-block", width: "1.1em", color: "var(--secondary)" },
  ".cm-live-task": { margin: "0 0.45em 0 0", verticalAlign: "-0.1em", cursor: "pointer" },
  ".cm-live-rule": { display: "inline-block", width: "100%", borderTop: "1px solid var(--separator)", verticalAlign: "middle" },
});

// --- math: $inline$ and $$display$$ typeset with KaTeX (raw while the cursor is in it) ---------
// A state field, not the plugin above: a $$ block may span lines, which only fields may replace.

class MathWidget extends WidgetType {
  constructor(
    readonly tex: string,
    readonly display: boolean,
    readonly at: number,
  ) {
    super();
  }
  eq(other: MathWidget) {
    return other.tex === this.tex && other.display === this.display && other.at === this.at;
  }
  toDOM(view: EditorView) {
    const el = document.createElement(this.display ? "div" : "span");
    el.className = this.display ? "cm-live-math block" : "cm-live-math";
    el.innerHTML = katex.renderToString(this.tex, { displayMode: this.display, throwOnError: false, output: "html" });
    el.title = "Click to edit the LaTeX";
    el.onmousedown = (e) => {
      e.preventDefault();
      view.dispatch({ selection: { anchor: this.at + (this.display ? 2 : 1) } });
      view.focus();
    };
    return el;
  }
  ignoreEvent() {
    return false;
  }
}

function inCode(state: EditorState, pos: number) {
  for (let n: { name: string; parent: unknown } | null = syntaxTree(state).resolveInner(pos, 1); n; n = n.parent as typeof n) {
    if (/Code/.test(n.name)) return true;
  }
  return false;
}

interface MathRange {
  from: number;
  to: number;
  tex: string;
  display: boolean;
  whole: boolean; // a $$ block on lines of its own (replaced as a block)
}

/** Every equation outside code (only when the text changes). */
function findMath(state: EditorState): MathRange[] {
  const text = state.doc.toString();
  const found: MathRange[] = [];
  const blocks: [number, number][] = [];
  for (const m of text.matchAll(/\$\$([\s\S]+?)\$\$/g)) {
    const from = m.index!;
    const to = from + m[0].length;
    blocks.push([from, to]);
    if (inCode(state, from)) continue;
    const whole = state.doc.lineAt(from).from === from && state.doc.lineAt(to).to === to;
    found.push({ from, to, tex: m[1].trim(), display: true, whole });
  }
  // Inline $…$ (not "$5 and $6"), outside $$ blocks and code.
  for (const m of text.matchAll(/(^|[^\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?!\d)/gm)) {
    const from = m.index! + m[1].length;
    const to = m.index! + m[0].length;
    if (blocks.some(([a, b]) => from >= a && from < b) || inCode(state, from)) continue;
    found.push({ from, to, tex: m[2], display: false, whole: false });
  }
  return found;
}

/** Typeset every equation the cursor / selection is not in (cheap: on every cursor move). */
function mathDecorations(state: EditorState, ranges: MathRange[]): DecorationSet {
  const touched = (r: MathRange) => state.selection.ranges.some((s) => s.from <= r.to && s.to >= r.from);
  return Decoration.set(
    ranges
      .filter((r) => !touched(r))
      .map((r) => Decoration.replace({ widget: new MathWidget(r.tex, r.display, r.from), block: r.whole }).range(r.from, r.to)),
    true,
  );
}

const mathField = StateField.define<{ ranges: MathRange[]; decorations: DecorationSet }>({
  create(state) {
    const ranges = findMath(state);
    return { ranges, decorations: mathDecorations(state, ranges) };
  },
  update(value, tr) {
    if (tr.docChanged) {
      const ranges = findMath(tr.state);
      return { ranges, decorations: mathDecorations(tr.state, ranges) };
    }
    return tr.selection ? { ranges: value.ranges, decorations: mathDecorations(tr.state, value.ranges) } : value;
  },
  provide: (field) => EditorView.decorations.from(field, (v) => v.decorations),
});

const mathLook = EditorView.baseTheme({
  ".cm-live-math": { cursor: "pointer", borderRadius: "4px", padding: "0 1px" },
  ".cm-live-math:hover": { background: "var(--hover)" },
  ".cm-live-math.block": { display: "block", textAlign: "center", padding: "6px 0", overflowX: "auto" },
});

/** The extension that turns Live mode on. */
export const livePreview = [plugin, look, mathField, mathLook];
