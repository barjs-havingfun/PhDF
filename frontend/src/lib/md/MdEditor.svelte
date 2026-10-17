<script lang="ts">
  // Markdown editor (CodeMirror 6) with an optional rendered preview. PhDF pins render as cards
  // with a "Go to PDF" button; Ctrl+click on a pin line works too.
  import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
  import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
  import { Compartment, EditorState, RangeSetBuilder } from "@codemirror/state";
  import {
    Decoration,
    EditorView,
    keymap,
    placeholder,
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
  import { api } from "../api";
  import EditorMenu from "./EditorMenu.svelte";
  import FormatBar, { type BarSide } from "./FormatBar.svelte";
  import { blockOf, insertLink, toggleInline, type Block } from "./format";
  import { notify } from "../notify.svelte";
  import { kbd } from "../platform";
  import { outsideClose } from "../outside";
  import { livePreview } from "./live";
  import { DEFAULT_SIZE, RANGES, loadTypography, setTextSize, setTextWidth, typo, typographyVars, widthLabel, zoomText } from "./typography.svelte";

  interface Props {
    md: MdDoc;
    topInset: number;
    onpin: (pin: Pin) => void;
    reveal?: { id: string; nonce: number; focus?: boolean } | null;
    actions?: Snippet;
  }

  let { md, topInset, onpin, reveal = null, actions }: Props = $props();

  // Edit: raw Markdown; Live: formatted except the lines being edited; Preview: rendered.
  type Mode = "edit" | "live" | "preview";
  let mode = $state<Mode>("edit");
  const liveConf = new Compartment();
  api()
    .then((py) => py.get_setting<Mode | null>("md.mode", null))
    .then((m) => m && (mode = m));

  function setMode(m: Mode) {
    mode = m;
    api().then((py) => py.set_setting("md.mode", m));
  }

  $effect(() => {
    const live = mode === "live";
    view?.dispatch({ effects: liveConf.reconfigure(live ? livePreview : []) });
  });
  let typeMenu = $state(false);
  let typeWrap = $state<HTMLElement>();
  $effect(() => {
    if (typeMenu) return outsideClose(() => typeWrap, () => (typeMenu = false));
  });
  loadTypography();
  let host: HTMLDivElement;
  let preview = $state<HTMLDivElement>();
  let view = $state<EditorView>();

  // Format bar (any side, remembered for all notes) and the right-click menu.
  let block = $state<Block>("body");
  let side = $state<BarSide>("top");
  let main = $state<HTMLDivElement>();
  let ctxMenu = $state<{ x: number; y: number } | null>(null);
  api()
    .then((py) => py.get_setting<BarSide | null>("md.formatBar", null))
    .then((s) => s && (side = s));

  function setSide(s: BarSide, done: boolean) {
    side = s;
    if (done) api().then((py) => py.set_setting("md.formatBar", s));
  }

  // Rename the file by clicking its name (not PhDF's own parking / grades files).
  let renaming = $state(false);
  let newName = $state("");
  let renameInput = $state<HTMLInputElement>();
  const fixedName = $derived(/\.(parking|grades)\.md$/i.test(md.path));

  async function startRename() {
    newName = md.name.replace(/\.md$/i, "");
    renaming = true;
    await Promise.resolve();
    renameInput?.select();
  }

  async function finishRename() {
    if (!renaming) return;
    renaming = false;
    const name = newName.trim();
    if (!name || name === md.name.replace(/\.md$/i, "")) return;
    try {
      await md.rename(name);
      notify.show({ text: `Renamed to ${md.name}` }, 1800);
    } catch (e) {
      notify.error(String(e).replace(/^Error: /, ""));
    }
  }

  // Zoom menu in the status line: slider, presets, reset.
  let zoomMenu = $state(false);
  let zoomWrap = $state<HTMLElement>();
  $effect(() => {
    if (zoomMenu) return outsideClose(() => zoomWrap, () => (zoomMenu = false));
  });

  const words = $derived(md.text.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)?.length ?? 0);

  // Ctrl+wheel zooms the note's text (non-passive, so the page itself doesn't zoom).
  let root = $state<HTMLDivElement>();
  $effect(() => {
    const el = root;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      zoomText(e.deltaY < 0 ? 1 : -1);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  function onEditorContext(e: MouseEvent) {
    e.preventDefault();
    ctxMenu = { x: e.clientX, y: e.clientY };
  }

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
    { tag: t.heading1, fontSize: "1.85em", fontWeight: "750", letterSpacing: "-0.01em" },
    { tag: t.heading2, fontSize: "1.5em", fontWeight: "700", letterSpacing: "-0.005em" },
    { tag: t.heading3, fontSize: "1.25em", fontWeight: "650" },
    { tag: t.heading4, fontSize: "1.1em", fontWeight: "600" },
    { tag: [t.heading5, t.heading6], fontWeight: "600", color: "var(--secondary)" },
    { tag: t.strong, fontWeight: "700" },
    { tag: t.emphasis, fontStyle: "italic" },
    { tag: t.strikethrough, textDecoration: "line-through" },
    { tag: [t.link, t.url], color: "var(--accent)" },
    {
      tag: t.monospace,
      fontFamily: 'ui-monospace, SFMono-Regular, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace',
      fontSize: "0.92em",
      backgroundColor: "var(--hover)",
      borderRadius: "4px",
    },
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
          markdown({ base: markdownLanguage }), // GitHub flavour: tables, tasks, ~~strike~~
          liveConf.of([]),
          syntaxHighlighting(highlight),
          theme,
          pinPlugin,
          pinClicks,
          keymap.of([
            { key: "Mod-b", run: (v) => (toggleInline(v, "bold"), true) },
            { key: "Mod-i", run: (v) => (toggleInline(v, "italic"), true) },
            { key: "Mod-Shift-x", run: (v) => (toggleInline(v, "strike"), true) },
            { key: "Mod-Shift-h", run: (v) => (toggleInline(v, "highlight"), true) },
            { key: "Mod-e", run: (v) => (toggleInline(v, "code"), true) },
            { key: "Mod-Shift-k", run: (v) => (insertLink(v), true) }, // Ctrl+K stays the command palette
            { key: "Mod-=", run: () => (zoomText(1), true) },
            { key: "Mod-+", run: () => (zoomText(1), true) },
            { key: "Mod--", run: () => (zoomText(-1), true) },
            { key: "Mod-0", run: () => (zoomText(0), true) },
          ]),
          placeholder("Start writing here… Use the bar above for headings, lists and more."),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) md.edit(u.state.doc.toString());
            if (u.selectionSet || u.docChanged) block = blockOf(u.state.doc.lineAt(u.state.selection.main.head).text);
            // Remember where the user writes (equations are inserted there).
            if ((u.selectionSet || u.docChanged) && u.view.hasFocus) md.cursor = u.state.selection.main.head;
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

  // Show an inserted block (e.g. an equation) and put the cursor after it.
  $effect(() => {
    const r = md.reveal;
    if (!r) return;
    queueMicrotask(() => {
      if (mode === "preview" && r.heading !== undefined) {
        const hs = preview?.querySelectorAll(":is(h1, h2, h3, h4, h5, h6)");
        hs?.[r.heading]?.scrollIntoView({ block: "start", behavior: "smooth" });
        return;
      }
      if (mode === "preview" || !view) return;
      const pos = Math.min(r.pos, view.state.doc.length);
      view.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: "center" }) });
    });
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

<div class="md-editor" style={typographyVars()} bind:this={root}>
  <header style="padding-top:{topInset}px">
    <div class="bar">
      {#if renaming}
        <input
          class="rename"
          bind:this={renameInput}
          bind:value={newName}
          onkeydown={(e) => (e.key === "Enter" ? finishRename() : e.key === "Escape" && (renaming = false))}
          onblur={finishRename}
          aria-label="New file name"
          spellcheck="false"
        />
      {:else}
        <button class="file" title={fixedName ? md.path : `${md.path}
Click to rename`} onclick={startRename} disabled={fixedName}>
          {md.name.replace(/\.md$/i, "")}<span class="ext">.md</span>
        </button>
      {/if}
      {@render actions?.()}
      <div class="aa" bind:this={typeWrap}>
        <button class="aa-btn" class:on={typeMenu} title="Font & spacing" onclick={() => (typeMenu = !typeMenu)}>Aa</button>
        {#if typeMenu}<TypographyMenu onclose={() => (typeMenu = false)} />{/if}
      </div>
      <div class="segmented" role="tablist">
        <button role="tab" aria-selected={mode === "edit"} onclick={() => setMode("edit")}>Edit</button>
        <button role="tab" aria-selected={mode === "live"} title="Formatted while you write; the line you edit shows its Markdown" onclick={() => setMode("live")}>Live</button>
        <button role="tab" aria-selected={mode === "preview"} onclick={() => setMode("preview")}>Preview</button>
      </div>
    </div>
  </header>

  <div class="main side-{side}" bind:this={main}>
    {#if mode !== "preview"}
      <FormatBar view={() => view} {block} {side} container={() => main} onside={setSide} />
    {/if}
    <div class="body">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="cm-host" class:hidden={mode === "preview"} bind:this={host} oncontextmenu={onEditorContext}></div>
      {#if mode === "preview"}
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
        <div class="preview" bind:this={preview} onclick={onPreviewClick}>
          <!-- markdown-it runs with html disabled, so user HTML is escaped -->
          {@html html}
        </div>
      {/if}
    </div>
  </div>
  <footer class="status">
    <span>{words} {words === 1 ? "word" : "words"} · {Math.max(1, Math.round(words / 220))} min read</span>
    <span class="grow"></span>
    <div class="zoom-wrap" bind:this={zoomWrap}>
      <button class="zoom" class:on={zoomMenu} title={kbd("Text size and width (size also Ctrl+wheel, Ctrl+= / Ctrl+-, Ctrl+0)")} onclick={() => (zoomMenu = !zoomMenu)}>
        {Math.round((typo.size / DEFAULT_SIZE) * 100)}%
      </button>
      {#if zoomMenu}
        <div class="zoom-menu" role="menu">
          <input
            type="range"
            min={RANGES.size.min}
            max={RANGES.size.max}
            value={typo.size}
            oninput={(e) => setTextSize(Number(e.currentTarget.value))}
            aria-label="Note text size"
          />
          <div class="presets">
            {#each [75, 100, 125, 150, 200] as p}
              <button class:on={Math.round((typo.size / DEFAULT_SIZE) * 100) === p} onclick={() => setTextSize((DEFAULT_SIZE * p) / 100)}>{p}%</button>
            {/each}
          </div>
          <button class="reset" onclick={() => zoomText(0)}>Reset to 100%</button>
          <div class="width-label">Text width <span>{widthLabel(typo.width)}</span></div>
          <input
            type="range"
            min={RANGES.width.min}
            max={RANGES.width.max}
            step={RANGES.width.step}
            value={typo.width}
            oninput={(e) => setTextWidth(Number(e.currentTarget.value))}
            aria-label="Note text width"
          />
          <div class="presets">
            {#each [["Narrow", 640], ["Wide", 1000], ["Full", RANGES.width.max]] as [label, w]}
              <button class:on={typo.width === w} onclick={() => setTextWidth(Number(w))}>{label}</button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
    <span class="saved" class:busy={md.saving || md.dirty}>{md.saving || md.dirty ? "Saving…" : md.exists ? "Saved ✓" : "Not saved yet"}</span>
  </footer>
</div>

{#if ctxMenu && view}
  <EditorMenu {view} path={md.path} {block} x={ctxMenu.x} y={ctxMenu.y} onclose={() => (ctxMenu = null)} />
{/if}

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
    border-radius: 8px;
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
    height: 40px;
    padding: 0 10px 0 14px;
  }

  .file {
    flex: 1;
    min-width: 0;
    padding: 3px 6px;
    margin-left: -6px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: text;
  }

  .file:hover:not(:disabled) {
    background: var(--hover);
  }

  .file:disabled {
    cursor: default;
  }

  .ext {
    font-weight: 400;
    color: var(--tertiary);
  }

  .rename {
    flex: 1;
    min-width: 0;
    height: 26px;
    padding: 0 8px;
    border: none;
    border-radius: 8px;
    background: var(--hover);
    color: var(--text);
    font: 600 13px var(--font);
    outline: none;
    box-shadow: 0 0 0 3px var(--focus-ring);
    user-select: text;
  }

  .status {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    height: 24px;
    padding: 0 12px;
    border-top: 0.5px solid var(--separator);
    font-size: 11px;
    color: var(--tertiary);
  }

  .status .grow {
    flex: 1;
  }

  .zoom {
    padding: 0 6px;
    border-radius: 5px;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    color: var(--tertiary);
  }

  .zoom-wrap {
    position: relative;
  }

  .zoom.on {
    background: var(--hover);
    color: var(--text);
  }

  /* Opens upward from the status line. */
  .zoom-menu {
    position: absolute;
    right: 0;
    bottom: calc(100% + 6px);
    z-index: 30;
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 220px;
    padding: 10px;
    border-radius: 13px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
    color: var(--text);
  }

  .zoom-menu input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
  }

  .zoom-menu .width-label {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--separator);
    font-size: 12px;
    color: var(--secondary);
  }

  .zoom-menu .presets {
    display: flex;
    gap: 4px;
  }

  .zoom-menu .presets button,
  .zoom-menu .reset {
    flex: 1;
    padding: 3px 0;
    border-radius: 6px;
    background: var(--hover);
    font-size: 11px;
  }

  .zoom-menu .presets button.on {
    background: var(--accent);
    color: var(--accent-text);
  }

  .zoom:hover {
    background: var(--hover);
    color: var(--text);
  }

  .saved {
    color: #34c759;
  }

  .saved.busy {
    color: var(--tertiary);
  }

  .segmented {
    flex: none;
    display: flex;
    padding: 2px;
    border-radius: 9px;
    background: var(--hover);
  }

  .segmented button {
    padding: 1px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--secondary);
  }

  .segmented button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  /* The format bar on any side of the text (FormatBar comes first in the markup). */
  .main {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .main.side-bottom {
    flex-direction: column-reverse;
  }

  .main.side-left {
    flex-direction: row;
  }

  .main.side-right {
    flex-direction: row-reverse;
  }

  .main.side-bottom :global(.fbar) {
    border-bottom: none;
    border-top: 0.5px solid var(--separator);
  }

  .main.side-left :global(.fbar) {
    border-right: 0.5px solid var(--separator);
  }

  .main.side-right :global(.fbar) {
    border-left: 0.5px solid var(--separator);
  }

  .body {
    position: relative;
    flex: 1;
    min-width: 0;
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

  /* Headings: a clear rhythm, a thin rule under the two biggest. */
  .preview :global(:is(h1, h2, h3, h4, h5, h6)) {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    line-height: 1.25;
  }
  .preview :global(h1) {
    font-size: 1.9em;
    font-weight: 750;
    letter-spacing: -0.01em;
    padding-bottom: 0.25em;
    border-bottom: 1px solid var(--separator);
  }
  .preview :global(h2) {
    font-size: 1.5em;
    font-weight: 700;
    padding-bottom: 0.2em;
    border-bottom: 0.5px solid var(--separator);
  }
  .preview :global(h3) {
    font-size: 1.25em;
  }
  .preview :global(h4) {
    font-size: 1.1em;
  }
  .preview :global(:is(h5, h6)) {
    font-size: 1em;
    color: var(--secondary);
  }
  .preview :global(> :first-child) {
    margin-top: 0.4em;
  }

  .preview :global(:is(p, ul, ol)) {
    margin-top: 0.4em;
    margin-bottom: 0.8em;
  }
  .preview :global(li + li) {
    margin-top: 0.2em;
  }

  /* Pins and their quotes: one soft card. */
  .preview :global(.pin-card) {
    display: block;
    width: 100%;
    max-width: var(--md-width);
    margin: 18px auto 0;
    padding: 7px 14px;
    border: none;
    border-left: 3px solid var(--accent);
    border-radius: 13px 13px 0 0;
    background: var(--pin-bg);
    color: var(--accent);
    font: 600 12px var(--font);
    text-align: left;
    cursor: pointer;
  }
  .preview :global(.pin-card:hover .pin-go) {
    text-decoration: underline;
  }
  .preview :global(.pin-card + blockquote) {
    margin-top: 0;
    border-left: 3px solid var(--accent);
    border-radius: 0 0 13px 13px;
    background: var(--pin-bg);
    padding: 6px 14px 8px;
    color: var(--secondary);
    font-style: italic;
  }

  .preview :global(blockquote) {
    padding: 2px 14px;
    border-left: 3px solid var(--separator);
    color: var(--secondary);
  }

  /* Callouts: > [!note] Title */
  .preview :global(.callout) {
    --c: #0a84ff;
    padding: 8px 14px 10px;
    border-left: 4px solid var(--c);
    border-radius: 10px;
    background: color-mix(in srgb, var(--c) 10%, transparent);
    color: var(--text);
    font-style: normal;
  }
  .preview :global(.callout-title) {
    margin: 0 0 0.3em;
    font-weight: 650;
    color: var(--c);
  }
  .preview :global(:is(.callout-tip, .callout-success)) {
    --c: #30b158;
  }
  .preview :global(:is(.callout-warning, .callout-question)) {
    --c: #f2a10a;
  }
  .preview :global(:is(.callout-danger, .callout-error)) {
    --c: #ff3b30;
  }
  .preview :global(:is(.callout-quote, .callout-example)) {
    --c: #8e8e93;
  }

  .preview :global(.math-block) {
    overflow-x: auto;
    margin: 0.8em 0;
  }

  .preview :global(code) {
    font-family: ui-monospace, SFMono-Regular, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace;
    font-size: 0.9em;
    background: var(--hover);
    padding: 1px 5px;
    border-radius: 6px;
  }
  .preview :global(pre) {
    padding: 12px 14px;
    border-radius: 13px;
    background: var(--hover);
    overflow-x: auto;
    line-height: 1.5;
  }
  .preview :global(pre code) {
    padding: 0;
    background: none;
  }

  /* Tables: rounded, zebra rows (the grades table too). */
  .preview :global(table) {
    display: block;
    width: max-content;
    max-width: 100%;
    overflow-x: auto;
    border-collapse: separate;
    border-spacing: 0;
    border: 0.5px solid var(--separator);
    border-radius: 13px;
    font-size: 0.95em;
  }
  .preview :global(:is(th, td)) {
    padding: 6px 12px;
    border-bottom: 0.5px solid var(--separator);
    text-align: left;
  }
  .preview :global(th) {
    background: var(--hover);
    font-weight: 600;
  }
  .preview :global(tr:last-child td) {
    border-bottom: none;
  }
  .preview :global(tbody tr:nth-child(even)) {
    background: color-mix(in srgb, var(--hover) 55%, transparent);
  }

  .preview :global(li.task) {
    list-style: none;
    margin-left: -1.3em;
  }
  .preview :global(li.task input) {
    margin: 0 0.5em 0 0;
    vertical-align: -0.1em;
  }

  .preview :global(hr) {
    border: none;
    border-top: 1px solid var(--separator);
    margin: 1.6em auto;
  }

  .preview :global(a) {
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
  }
  .preview :global(a:hover) {
    border-bottom-color: var(--accent);
  }

  .preview :global(img) {
    max-width: 100%;
    border-radius: 10px;
  }

  .preview :global(mark) {
    background: rgb(255 214 10 / 0.4);
    color: inherit;
    border-radius: 2px;
    padding: 0 1px;
  }

  .preview :global(.footnotes) {
    margin-top: 2.5em;
    padding-top: 0.6em;
    border-top: 0.5px solid var(--separator);
    font-size: 0.9em;
    color: var(--secondary);
  }
  .preview :global(sup.fn a) {
    border: none;
    font-size: 0.8em;
  }

  @keyframes -global-pin-flash {
    from {
      background-color: rgb(255 214 10 / 0.55);
    }
  }
</style>
