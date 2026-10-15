<script lang="ts">
  // One pane: its tab bar (overlaying the top, under the window toolbar) and the active tab —
  // a PDF (with annotations panel and, optionally, its integrated note beside it), a standalone
  // Markdown note, or the welcome page. Shows drop zones while a tab is being dragged.
  import type { Annotation, PdfLink, RecentDocument } from "./api";
  import AnnotationsPanel from "./annot/AnnotationsPanel.svelte";
  import AnnotEditor from "./annot/AnnotEditor.svelte";
  import SelectionMenu from "./annot/SelectionMenu.svelte";
  import { capture, drag } from "./dnd.svelte";
  import Icon from "./Icon.svelte";
  import AiPanel from "./ai/AiPanel.svelte";
  import { HEADER_HEIGHT, saveLayout, term } from "./ai/terminal.svelte";
  import { notify } from "./notify.svelte";
  import { ocrLanguages } from "./ocr";
  import type { Pin } from "./pin";
  import type { AnyTab, MdTab, Tab } from "./tab.svelte";
  import TabBar from "./TabBar.svelte";
  import Viewer, { type TextSelection } from "./viewer/Viewer.svelte";
  import Welcome from "./Welcome.svelte";
  import type { Pane } from "./workspace.svelte";

  interface Props {
    pane: Pane;
    focused: boolean;
    multi: boolean; // more than one pane in the window
    zen: boolean; // hide the tab bar
    termHere: boolean; // the AI terminal is docked in this pane's side column
    toolbarHeight: number;
    invert: boolean;
    version: string;
    recents: RecentDocument[];
    onfocus: () => void;
    onopen: () => void;
    onnewnote: () => void;
    onopenpath: (path: string) => void;
    onselect: (tab: AnyTab) => void;
    onclose: (tab: AnyTab) => void;
    onnew: () => void;
    ondragstart: (e: PointerEvent, tab: AnyTab) => void;
    onlink: (link: PdfLink, event: MouseEvent) => void;
    onviewer: (viewer: Viewer | undefined) => void;
    /** A pin was clicked in a standalone note: open its PDF there. */
    onmdpin: (tab: MdTab, pin: Pin) => void;
    onpickmd: () => Promise<string | null>;
  }

  let {
    pane, focused, multi, zen, termHere, toolbarHeight, invert, version, recents,
    onfocus, onopen, onnewnote, onopenpath, onselect, onclose, onnew, ondragstart, onlink, onviewer,
    onmdpin, onpickmd,
  }: Props = $props(); // prettier-ignore

  let barHeight = $state(34);
  let viewer = $state<Viewer>();
  let content = $state<HTMLElement>();

  const active = $derived(pane.active);
  const pdf = $derived(active?.kind === "pdf" ? (active as Tab) : null);
  const note = $derived(active?.kind === "md" ? (active as MdTab) : null);
  const topInset = $derived(zen ? 0 : toolbarHeight + barHeight);

  // Delete / Backspace removes the selected annotation (unless typing somewhere).
  function onKeydown(e: KeyboardEvent) {
    if (!focused || !pdf?.selectedAnnot || (e.key !== "Delete" && e.key !== "Backspace")) return;
    const el = e.target as HTMLElement;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable) return;
    e.preventDefault();
    const id = pdf.selectedAnnot;
    editing = null;
    pdf.deleteAnnotation(id);
  }

  // The Markdown editor (CodeMirror) is loaded on first use, keeping PDF-only startup light.
  const loadEditor = () => import("./md/MdEditor.svelte").then((m) => m.default);

  $effect(() => onviewer(viewer));

  // Scanned pages: offer OCR when the current page has no text (checked per page, lazily).
  $effect(() => {
    pdf?.checkText(pdf.page);
  });
  const pageHasNoText = $derived(pdf ? pdf.hasText[pdf.page] === false : false);
  let ocrDismissed = $state(false);

  async function recognize(all: boolean) {
    if (!pdf) return;
    const tab = pdf;
    try {
      const langs = await ocrLanguages();
      if (all) await tab.loadNoTextPages();
      await tab.runOcr(all ? [...(tab.noTextPages ?? [])] : [tab.page], langs);
      notify.show({ text: "Text recognized. Save with Ctrl+S to keep it in the PDF." });
    } catch (e) {
      notify.error(`OCR failed: ${e}`);
    }
  }

  // Floating UI over the PDF.
  let selection = $state<TextSelection | null>(null);
  let editing = $state<{ annot: Annotation; anchor: DOMRect } | null>(null);
  let placing = $state<{ kind: "note" | "freetext"; page: number; x: number; y: number; anchor: DOMRect } | null>(null);

  // Close floating UI when the tab changes.
  $effect(() => {
    void active;
    selection = null;
    editing = null;
    placing = null;
  });

  function onAnnot(annot: Annotation, e: MouseEvent) {
    if (!pdf) return;
    pdf.selectedAnnot = annot.id;
    editing = { annot, anchor: new DOMRect(e.clientX - 1, e.clientY - 1, 2, 2) };
    // PDF → note: show its pin if the integrated note is open.
    if (pdf.mdOpen && pdf.hasPin(annot.id)) pdf.mdReveal = { id: annot.id, nonce: Date.now() };
  }

  function onPlace(page: number, x: number, y: number, e: MouseEvent) {
    if (!pdf || pdf.tool === "select") return;
    placing = { kind: pdf.tool === "note" ? "note" : "freetext", page, x, y, anchor: new DOMRect(e.clientX - 1, e.clientY - 1, 2, 2) };
  }

  function onPin(pin: Pin) {
    pdf?.reveal(pin.id, pin.page);
  }

  /** Open items in the document's parking lot (for the tab badge). */
  function openParked(tab: Tab) {
    return tab.parking ? (tab.parking.text.match(/^- \[ \] /gm)?.length ?? 0) : 0;
  }

  async function linkExisting() {
    const path = await onpickmd();
    if (path && pdf) await pdf.linkExistingMd(path);
  }

  const mdShown = $derived(!!(pdf?.mdOpen && pdf.md));
  const sideShown = $derived(mdShown || termHere);
  const sideWidth = $derived(mdShown && pdf ? pdf.mdWidth : term.sideWidth);

  // Divider between the document and the side column (note and/or terminal).
  function startMdResize(e: PointerEvent) {
    if (!content) return;
    const tab = pdf;
    const el = e.currentTarget as HTMLElement;
    const box = content.getBoundingClientRect();
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      const w = Math.min(Math.max((box.right - ev.clientX) / box.width, 0.2), 0.75);
      if (mdShown && tab) tab.mdWidth = w;
      else term.sideWidth = w;
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      saveLayout();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  // Divider between the terminal (top) and the note (bottom): a drawer you can pull shut.
  let side = $state<HTMLElement>();
  function startTermResize(e: PointerEvent) {
    if (!side) return;
    const el = e.currentTarget as HTMLElement;
    const box = side.getBoundingClientRect();
    const top = box.top + topInset;
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      const f = (ev.clientY - top) / (box.bottom - top);
      if (f < 0.06) term.collapsed = true;
      else {
        term.collapsed = false;
        term.sideFraction = Math.min(f, 0.9);
      }
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      saveLayout();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  const termSlotStyle = $derived(
    term.collapsed
      ? `height:${topInset + HEADER_HEIGHT}px;flex:none`
      : mdShown
        ? `height:calc(${topInset}px + (100% - ${topInset}px) * ${term.sideFraction});flex:none`
        : "flex:1",
  );

  const zone = $derived.by(() => {
    const t = drag.target;
    if (!t || !("paneId" in t) || t.paneId !== pane.id || t.kind === "bar") return null;
    return t.kind === "split" ? t.side : "into";
  });
</script>

<svelte:window onkeydown={onKeydown} />

<section
  class="pane"
  style="flex:{pane.width} 1 0;--focus-mark:{multi ? 1 : 0}"
  data-pane-body={pane.id}
  onpointerdowncapture={onfocus}
>
  {#if !zen}
    <div class="bar" style="top:{toolbarHeight}px" bind:clientHeight={barHeight}>
      <TabBar {pane} focused={focused && multi} {onselect} {onclose} {onnew} {ondragstart} />
    </div>
  {/if}

  {#if pdf}
    {#key pdf.id}
      <div class="content" bind:this={content}>
        <div class="doc">
          <Viewer
            bind:this={viewer}
            tab={pdf}
            {topInset}
            {invert}
            {onlink}
            onselection={(s) => (selection = s)}
            onannot={onAnnot}
            onplace={onPlace}
          />
          <AnnotationsPanel tab={pdf} {topInset} />
        </div>
        {#if sideShown}
          <div class="md-divider" role="separator" aria-orientation="vertical" onpointerdown={startMdResize}></div>
          <div class="side" style="flex-basis:{sideWidth * 100}%" bind:this={side}>
          {#if termHere}
            <div class="term-slot" style={termSlotStyle}><AiPanel {topInset} /></div>
            {#if mdShown && !term.collapsed}
              <div class="h-divider" role="separator" aria-orientation="horizontal" onpointerdown={startTermResize}></div>
            {/if}
          {/if}
          {#if mdShown && pdf.md}
          <div class="md">
            {#await loadEditor() then MdEditor}
            {#key pdf.mdView}
            <MdEditor
              md={pdf.mdView === "parking" && pdf.parking ? pdf.parking : pdf.md}
              topInset={termHere ? 0 : topInset}
              onpin={onPin}
              reveal={pdf.mdView === "note" ? pdf.mdReveal : null}
            >
              {#snippet actions()}
                <div class="views" role="tablist">
                  <button role="tab" aria-selected={pdf.mdView === "note"} onclick={() => pdf.setMdView("note")}>Note</button>
                  <button role="tab" aria-selected={pdf.mdView === "parking"} onclick={() => pdf.setMdView("parking")}>
                    Parking{#if openParked(pdf)}<span class="badge">{openParked(pdf)}</span>{/if}
                  </button>
                </div>
                <button class="md-btn" title="Link an existing .md file to this PDF" onclick={linkExisting}>
                  <Icon name="link" size={14} />
                </button>
                <button class="md-btn" title="Close note" onclick={() => pdf.toggleMd(false)}>
                  <Icon name="close" size={13} />
                </button>
              {/snippet}
            </MdEditor>
            {/key}
            {/await}
          </div>
          {/if}
          </div>
        {/if}
      </div>
    {/key}
  {:else if note}
    {#key note.id}
      <div class="content">
        <div class="md full">
          {#await loadEditor() then MdEditor}
            <MdEditor md={note.md} {topInset} onpin={(pin) => onmdpin(note, pin)} />
          {/await}
        </div>
        {#if termHere}
          <div class="md-divider" role="separator" aria-orientation="vertical" onpointerdown={startMdResize}></div>
          <div class="side" style="flex-basis:{term.sideWidth * 100}%"><div class="term-slot" style="flex:1"><AiPanel {topInset} /></div></div>
        {/if}
      </div>
    {/key}
  {:else}
    <div class="content" bind:this={content}>
      <div class="home-wrap">
        <div class="home" style="padding-top:{topInset + 24}px">
          <Welcome {version} {recents} {onopen} {onnewnote} {onopenpath} />
        </div>
      </div>
      {#if termHere}
        <div class="md-divider" role="separator" aria-orientation="vertical" onpointerdown={startMdResize}></div>
        <div class="side" style="flex-basis:{term.sideWidth * 100}%"><div class="term-slot" style="flex:1"><AiPanel {topInset} /></div></div>
      {/if}
    </div>
  {/if}

  {#if zone}
    <div class="drop {zone}" style="top:{topInset}px"></div>
  {/if}

  {#if pdf?.ocrProgress}
    <div class="ocr-bar" style="top:{topInset + 10}px">
      <span class="spinner"></span>
      Recognizing text… {pdf.ocrProgress.done}/{pdf.ocrProgress.total}
      <button onclick={() => pdf.stopOcr()}>Stop</button>
    </div>
  {:else if pdf && pageHasNoText && !ocrDismissed}
    <div class="ocr-bar" style="top:{topInset + 10}px">
      <Icon name="scan" size={16} />
      This page has no text.
      <button class="primary" onclick={() => recognize(false)}>Recognize Text</button>
      {#if pdf.pageCount > 1}
        <button onclick={() => recognize(true)} disabled={pdf.scanningText}>
          {pdf.scanningText ? "Finding pages…" : "All Pages Without Text"}
        </button>
      {/if}
      <button class="x" onclick={() => (ocrDismissed = true)} aria-label="Dismiss"><Icon name="close" size={12} /></button>
    </div>
  {/if}

  {#if pdf && selection}
    <SelectionMenu tab={pdf} sel={selection} onclose={() => (selection = null)} />
  {/if}
  {#if pdf && editing}
    {#key editing.annot.id}
      <AnnotEditor tab={pdf} anchor={editing.anchor} annot={editing.annot} onclose={() => (editing = null)} />
    {/key}
  {/if}
  {#if pdf && placing}
    <AnnotEditor tab={pdf} anchor={placing.anchor} {placing} onclose={() => (placing = null)} />
  {/if}
</section>

<style>
  .pane {
    position: relative;
    min-width: 220px;
    overflow: hidden;
  }

  .bar {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 9;
    background: var(--toolbar);
    backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 0.5px solid var(--separator);
  }

  .content {
    position: absolute;
    inset: 0;
    display: flex;
  }

  .doc {
    position: relative;
    flex: 1 1 0;
    min-width: 200px;
    overflow: hidden;
  }

  .side {
    position: relative;
    flex: 0 0 auto;
    min-width: 240px;
    display: flex;
    flex-direction: column;
  }

  .md {
    position: relative;
    flex: 1 1 0;
    min-height: 0;
  }

  .md.full {
    flex: 1 1 0;
  }

  .term-slot {
    position: relative;
    min-height: 0;
  }

  .h-divider {
    position: relative;
    z-index: 8;
    flex: none;
    height: 1px;
    background: var(--separator);
    cursor: row-resize;
  }

  .h-divider::before {
    content: "";
    position: absolute;
    inset: -4px 0;
  }

  .home-wrap {
    position: relative;
    flex: 1 1 0;
    min-width: 0;
  }

  .md-divider {
    position: relative;
    z-index: 8;
    flex: none;
    width: 1px;
    background: var(--separator);
    cursor: col-resize;
  }

  .md-divider::before {
    content: "";
    position: absolute;
    inset: 0 -4px;
  }

  .views {
    display: flex;
    padding: 2px;
    border-radius: 7px;
    background: var(--hover);
    margin-right: 4px;
  }

  .views button {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 1px 9px;
    border-radius: 5px;
    font-size: 12px;
    color: var(--secondary);
  }

  .views button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  .badge {
    min-width: 16px;
    padding: 0 4px;
    border-radius: 8px;
    background: var(--accent);
    color: var(--accent-text);
    font-size: 10px;
    line-height: 16px;
    text-align: center;
  }

  .md-btn {
    display: grid;
    place-items: center;
    width: 26px;
    height: 24px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .md-btn:hover {
    background: var(--hover);
    color: var(--text);
  }

  .home {
    position: absolute;
    inset: 0;
    overflow: auto;
    padding: 0 24px 32px;
    background: var(--window);
  }

  .ocr-bar {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    z-index: 8;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 6px 5px 12px;
    border-radius: 10px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 6px 20px rgb(0 0 0 / 0.18);
    font-size: 12px;
    white-space: nowrap;
  }

  .ocr-bar button {
    padding: 2px 10px;
    border-radius: 6px;
    background: var(--hover);
  }

  .ocr-bar button.primary {
    background: var(--accent);
    color: var(--accent-text);
  }

  .ocr-bar button.x {
    display: grid;
    place-items: center;
    padding: 0;
    width: 22px;
    height: 22px;
    background: none;
    color: var(--secondary);
  }

  .spinner {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid var(--separator);
    border-top-color: var(--accent);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .drop {
    position: absolute;
    bottom: 8px;
    z-index: 8;
    border-radius: 10px;
    background: rgb(0 122 255 / 0.14);
    outline: 2px solid var(--accent);
    outline-offset: -2px;
    pointer-events: none;
    transition: all 0.12s ease-out;
  }

  .drop.left {
    left: 8px;
    right: 50%;
  }

  .drop.right {
    left: 50%;
    right: 8px;
  }

  .drop.into {
    left: 8px;
    right: 8px;
  }
</style>
