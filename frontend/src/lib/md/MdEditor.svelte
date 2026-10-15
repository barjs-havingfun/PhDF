<script lang="ts">
  // Markdown editor (CodeMirror 6) with an optional rendered preview. PhDF pins render as cards
  // with a "Go to PDF" button; Ctrl+click on a pin line works too.
  import { markdown } from "@codemirror/lang-markdown";
  import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
  import { EditorState, RangeSetBuilder } from "@codemirror/state";
  import {
    Decoration,
    EditorView,
    ViewPlugin,
    WidgetType,
    type DecorationSet,
    type ViewUpdate,
  } from "@codemirror/view";
  import { tags as t } from "@lezer/highlight";
  import { minimalSetup } from "codemirror";
  import type { Snippet } from "svelte";
  import { onMount } from "svelte";
  import type { MdDoc } from "../md.svelte";
  import { parsePin, PIN_MARK, type Pin } from "../pin";
  import { renderMarkdown } from "./render";
  import TypographyMenu from "./TypographyMenu.svelte";
  import { loadTypography, typographyVars } from "./typography.svelte";

  interface Props {
    md: MdDoc;
    topInset: number;
    onpin: (pin: Pin) => void;
    reveal?: { id: string; nonce: number; focus?: boolean } | null;
    actions?: Snippet;
  }

  let { md, topInset, onpin, reveal = null, actions }: Props = $props();

  let mode = $state<"edit" | "preview">("edit");
  let typeMenu = $state(false);
  loadTypography();
  let host: HTMLDivElement;
  let preview = $state<HTMLDivElement>();
  let view: EditorView | undefined;

  // --- pins as cards ---------------------------------------------------------------------------

  class GoWidget extends WidgetType {
    readonly pin: Pin;
    constructor(pin: Pin) {
      super();
      this.pin = pin;
    }
    eq(other: GoWidget) {
      return other.pin.id === this.pin.id && other.pin.page === this.pin.page;
    }
    toDOM() {
      const b = document.createElement("button");
      b.className = "cm-pin-go";
      b.textContent = "Go to PDF ↗";
      b.dataset.pinId = this.pin.id;
      b.dataset.pinPage = String(this.pin.page);
      return b;
    }
    ignoreEvent() {
      return false;
    }
  }

  function pinDecorations(v: EditorView): DecorationSet {
    const builder = new RangeSetBuilder<Decoration>();
    for (const { from, to } of v.visibleRanges) {
      let pos = from;
      let inQuote = false;
      while (pos <= to) {
        const line = v.state.doc.lineAt(pos);
        const pin = line.text.startsWith(PIN_MARK) ? parsePin(line.text, line.number) : null;
        if (pin) {
          builder.add(line.from, line.from, Decoration.line({ class: "cm-pin" }));
          builder.add(line.to, line.to, Decoration.widget({ widget: new GoWidget(pin), side: 1 }));
          inQuote = true;
        } else if (inQuote && line.text.startsWith(">")) {
          builder.add(line.from, line.from, Decoration.line({ class: "cm-pin-quote" }));
        } else {
          inQuote = false;
        }
        pos = line.to + 1;
      }
    }
    return builder.finish();
  }

  const pinPlugin = ViewPlugin.fromClass(
    class {
      decorations: DecorationSet;
      constructor(v: EditorView) {
        this.decorations = pinDecorations(v);
      }
      update(u: ViewUpdate) {
        if (u.docChanged || u.viewportChanged) this.decorations = pinDecorations(u.view);
      }
    },
    { decorations: (p) => p.decorations },
  );

  const pinClicks = EditorView.domEventHandlers({
    mousedown(e, v) {
      const go = (e.target as HTMLElement).closest<HTMLElement>(".cm-pin-go");
      if (go) {
        e.preventDefault();
        onpin({ id: go.dataset.pinId!, page: Number(go.dataset.pinPage), section: null, line: 0 });
        return true;
      }
      if (e.ctrlKey || e.metaKey) {
        const pos = v.posAtCoords({ x: e.clientX, y: e.clientY });
        const pin = pos !== null ? parsePin(v.state.doc.lineAt(pos).text) : null;
        if (pin) {
          e.preventDefault();
          onpin(pin);
          return true;
        }
      }
      return false;
    },
  });

  // --- look ------------------------------------------------------------------------------------

  const highlight = HighlightStyle.define([
    { tag: t.heading1, fontSize: "1.6em", fontWeight: "700" },
    { tag: t.heading2, fontSize: "1.35em", fontWeight: "650" },
    { tag: t.heading3, fontSize: "1.15em", fontWeight: "600" },
    { tag: [t.heading4, t.heading5, t.heading6], fontWeight: "600" },
    { tag: t.strong, fontWeight: "700" },
    { tag: t.emphasis, fontStyle: "italic" },
    { tag: t.strikethrough, textDecoration: "line-through" },
    { tag: [t.link, t.url], color: "var(--accent)" },
    { tag: t.monospace, fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace" },
    { tag: t.quote, color: "var(--secondary)", fontStyle: "italic" },
    { tag: [t.processingInstruction, t.meta], color: "var(--tertiary)" },
  ]);

  const theme = EditorView.theme({
    "&": { height: "100%", fontSize: "var(--md-size)", color: "var(--text)", backgroundColor: "transparent" },
    ".cm-scroller": {
      fontFamily: "var(--md-font)",
      lineHeight: "var(--md-line)",
      letterSpacing: "var(--md-letter)",
      padding: "8px 0 40vh",
    },
    ".cm-content": { maxWidth: "var(--md-width)", margin: "0 auto", padding: "0 28px", caretColor: "var(--accent)" },
    "&.cm-focused": { outline: "none" },
    ".cm-cursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
      backgroundColor: "rgb(0 122 255 / 0.22) !important",
    },
    ".cm-pin": {
      background: "var(--pin-bg)",
      borderLeft: "3px solid var(--accent)",
      borderRadius: "6px 6px 0 0",
      color: "var(--accent)",
      fontSize: "12px",
      fontWeight: "600",
      paddingTop: "3px",
      paddingBottom: "3px",
      marginTop: "6px",
    },
    ".cm-pin-quote": {
      background: "var(--pin-bg)",
      borderLeft: "3px solid var(--accent)",
      color: "var(--secondary)",
      fontStyle: "italic",
    },
    ".cm-pin-go": {
      float: "right",
      font: "500 11px var(--font)",
      color: "var(--accent)",
      background: "none",
      border: "none",
      padding: "0 4px",
      cursor: "pointer",
    },
    ".cm-pin-go:hover": { textDecoration: "underline" },
    ".cm-line.flash": { animation: "pin-flash 1.2s ease-out" },
  });

  // --- sync with the document --------------------------------------------------------------------

  onMount(() => {
    view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: md.text,
        extensions: [
          minimalSetup,
          EditorView.lineWrapping,
          markdown(),
          syntaxHighlighting(highlight),
          theme,
          pinPlugin,
          pinClicks,
          EditorView.updateListener.of((u) => {
            if (u.docChanged) md.edit(u.state.doc.toString());
          }),
        ],
      }),
    });
    return () => {
      md.flush();
      view?.destroy();
    };
  });

  // Text replaced from outside (load, reload, inserted pin): push it into the editor.
  $effect(() => {
    void md.revision;
    const text = md.text;
    if (view && view.state.doc.toString() !== text) {
      const head = Math.min(view.state.selection.main.head, text.length);
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text }, selection: { anchor: head } });
    }
  });

  // Scroll to a pin (and put the cursor on the empty line under it when asked to focus).
  $effect(() => {
    if (!reveal) return;
    const { id, focus } = reveal;
    queueMicrotask(() => revealPin(id, !!focus));
  });

  function revealPin(id: string, focus: boolean) {
    if (mode === "preview") {
      preview?.querySelector(`[data-pin-id="${id}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    if (!view) return;
    const doc = view.state.doc;
    for (let n = 1; n <= doc.lines; n++) {
      const line = doc.line(n);
      if (!line.text.includes(`#${id}`) || !parsePin(line.text)) continue;
      let next = n + 1;
      while (next <= doc.lines && doc.line(next).text.startsWith(">")) next++;
      // Skip the blank line too: text right under a quote would continue the quote.
      if (next < doc.lines && doc.line(next).text === "") next++;
      const caret = next <= doc.lines ? doc.line(next).from : doc.length;
      view.dispatch({
        selection: { anchor: focus ? caret : line.from },
        effects: EditorView.scrollIntoView(line.from, { y: "center" }),
      });
      if (focus) view.focus();
      requestAnimationFrame(() => {
        const el = view!.domAtPos(line.from).node;
        const lineEl = (el instanceof HTMLElement ? el : el.parentElement)?.closest(".cm-line");
        lineEl?.classList.add("flash");
        setTimeout(() => lineEl?.classList.remove("flash"), 1300);
      });
      return;
    }
  }

  function onPreviewClick(e: MouseEvent) {
    const card = (e.target as HTMLElement).closest<HTMLElement>("[data-pin-id]");
    if (card) onpin({ id: card.dataset.pinId!, page: Number(card.dataset.pinPage), section: null, line: 0 });
  }

  const html = $derived(mode === "preview" ? renderMarkdown(md.text) : "");
</script>

<div class="md-editor" style={typographyVars()}>
  <header style="padding-top:{topInset}px">
    <div class="bar">
      <span class="file" title={md.path}>
        {md.name}
        {#if md.saving}<span class="state">Saving…</span>{:else if !md.exists}<span class="state">New</span>{/if}
      </span>
      {@render actions?.()}
      <div class="aa">
        <button class="aa-btn" class:on={typeMenu} title="Font & spacing" onclick={() => (typeMenu = !typeMenu)}>Aa</button>
        {#if typeMenu}<TypographyMenu onclose={() => (typeMenu = false)} />{/if}
      </div>
      <div class="segmented" role="tablist">
        <button role="tab" aria-selected={mode === "edit"} onclick={() => (mode = "edit")}>Edit</button>
        <button role="tab" aria-selected={mode === "preview"} onclick={() => (mode = "preview")}>Preview</button>
      </div>
    </div>
  </header>

  <div class="body">
    <div class="cm-host" class:hidden={mode !== "edit"} bind:this={host}></div>
    {#if mode === "preview"}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="preview" bind:this={preview} onclick={onPreviewClick}>
        <!-- markdown-it runs with html disabled, so user HTML is escaped -->
        {@html html}
      </div>
    {/if}
  </div>
</div>

<style>
  .md-editor {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    background: var(--surface);
  }

  /* The note's header shrinks with its pane: file name first, then tighter buttons. */
  header {
    container: mdbar / inline-size;
    flex: none;
    background: var(--surface);
    border-bottom: 0.5px solid var(--separator);
  }

  .aa {
    position: relative;
  }

  .bar > :global(*) {
    flex-shrink: 0;
  }

  .bar > .file {
    flex-shrink: 1;
  }

  @container mdbar (max-width: 540px) {
    .file {
      display: none;
    }
    .bar {
      justify-content: flex-end;
    }
  }

  @container mdbar (max-width: 440px) {
    .bar {
      gap: 4px;
      padding: 0 6px;
    }
    .segmented button,
    .bar :global(.views button) {
      padding: 1px 6px;
      font-size: 11px;
    }
  }

  @container mdbar (max-width: 380px) {
    .bar :global(.md-btn[title^="Link"]) {
      display: none;
    }
  }

  .aa-btn {
    height: 24px;
    padding: 0 8px;
    border-radius: 6px;
    font: 600 13px/1 Georgia, serif;
    color: var(--secondary);
  }

  .aa-btn:hover,
  .aa-btn.on {
    background: var(--hover);
    color: var(--text);
  }

  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 36px;
    padding: 0 10px 0 14px;
  }

  .file {
    flex: 1;
    min-width: 0;
    font-weight: 600;
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .state {
    margin-left: 6px;
    font-weight: 400;
    color: var(--tertiary);
  }

  .segmented {
    flex: none;
    display: flex;
    padding: 2px;
    border-radius: 7px;
    background: var(--hover);
  }

  .segmented button {
    padding: 1px 10px;
    border-radius: 5px;
    font-size: 12px;
    color: var(--secondary);
  }

  .segmented button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  .body {
    position: relative;
    flex: 1;
    min-height: 0;
  }

  .cm-host {
    position: absolute;
    inset: 0;
    user-select: text;
    cursor: text;
  }

  .cm-host.hidden {
    display: none;
  }

  .preview {
    position: absolute;
    inset: 0;
    overflow: auto;
    padding: 16px 28px 40vh;
    user-select: text;
    cursor: auto;
    font-family: var(--md-font);
    line-height: var(--md-line);
    letter-spacing: var(--md-letter);
    font-size: var(--md-size);
  }

  .preview :global(> *) {
    max-width: var(--md-width);
    margin-left: auto;
    margin-right: auto;
  }

  .preview :global(.pin-card) {
    display: block;
    width: 100%;
    max-width: var(--md-width);
    margin: 14px auto 0;
    padding: 6px 12px;
    border-left: 3px solid var(--accent);
    border-radius: 6px 6px 0 0;
    background: var(--pin-bg);
    color: var(--accent);
    font: 600 12px var(--font);
    text-align: left;
    cursor: pointer;
  }

  .preview :global(.pin-card + blockquote) {
    margin-top: 0;
    border-left: 3px solid var(--accent);
    border-radius: 0 0 6px 6px;
    background: var(--pin-bg);
    padding: 4px 12px 6px;
    color: var(--secondary);
    font-style: italic;
  }

  .preview :global(blockquote) {
    margin-left: auto;
    padding-left: 12px;
    border-left: 3px solid var(--separator);
    color: var(--secondary);
  }

  .preview :global(code) {
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 0.92em;
    background: var(--hover);
    padding: 1px 4px;
    border-radius: 4px;
  }

  .preview :global(a) {
    color: var(--accent);
  }

  @keyframes -global-pin-flash {
    from {
      background-color: rgb(255 214 10 / 0.55);
    }
  }
</style>
