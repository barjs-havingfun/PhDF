<script lang="ts">
  // Edit an annotation (colour, comment, delete, link to the note) — or, with `placing`, write
  // the text of a new sticky note / free text before it is created.
  import { untrack } from "svelte";
  import type { Annotation } from "../api";
  import Icon from "../Icon.svelte";
  import type { Tab } from "../tab.svelte";
  import { COLORS, DEFAULT_COLOR, KIND_LABEL } from "./colors";
  import Popover from "./Popover.svelte";

  interface Placing {
    kind: "note" | "freetext";
    page: number;
    x: number;
    y: number;
  }

  interface Props {
    tab: Tab;
    anchor: { left: number; top: number; bottom: number; width: number };
    annot?: Annotation | null;
    placing?: Placing | null;
    onclose: () => void;
  }

  let { tab, anchor, annot = null, placing = null, onclose }: Props = $props();

  const isNew = $derived(!annot);
  const kind = $derived(annot?.kind ?? placing?.kind ?? "note");
  // Editable copies, seeded once from the annotation (the editor is re-created per annotation).
  let text = $state(untrack(() => annot?.contents ?? ""));
  let color = $state(
    untrack(() => annot?.color ?? (placing?.kind === "freetext" ? "#1d1d1f" : DEFAULT_COLOR)),
  );
  let field = $state<HTMLTextAreaElement>();

  const bodyLabel = $derived(kind === "note" || kind === "freetext" ? "Text" : "Comment");
  const markup = $derived(kind === "highlight" || kind === "underline" || kind === "strikeout");
  const hasPin = $derived(annot ? tab.hasPin(annot.id) : false);

  $effect(() => {
    if (placing) field?.focus();
  });

  async function commit() {
    if (placing) {
      if (!text.trim()) return onclose();
      const size = placing.kind === "note" ? 20 : 0;
      const w = Math.max(80, Math.min(260, text.length * 6.5 + 16));
      const lines = Math.max(1, text.split("\n").length);
      const rect: [number, number, number, number] =
        placing.kind === "note"
          ? [placing.x, placing.y, placing.x + size, placing.y + size]
          : [placing.x, placing.y, placing.x + w, placing.y + 18 * lines + 6];
      const created = await tab.addAnnotation(placing.page, placing.kind, [rect], color, text);
      tab.selectedAnnot = created.id;
      tab.tool = "select";
      return onclose();
    }
    if (annot && text !== annot.contents) await tab.updateAnnotation(annot.id, null, text);
    onclose();
  }

  async function recolor(value: string) {
    color = value;
    if (annot) await tab.updateAnnotation(annot.id, value, null);
  }

  async function remove() {
    if (annot) await tab.deleteAnnotation(annot.id);
    onclose();
  }

  async function toNote() {
    if (!annot) return;
    if (text !== annot.contents) await tab.updateAnnotation(annot.id, null, text);
    if (hasPin) {
      tab.mdOpen = true;
      await tab.ensureMd();
      tab.mdReveal = { id: annot.id, nonce: Date.now() };
    } else await tab.noteInMd(annot);
    onclose();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      commit();
    }
  }
</script>

<Popover {anchor} width={290} onclose={placing ? onclose : commit}>
  <div class="head">
    <span class="kind">{isNew ? `New ${KIND_LABEL[kind].toLowerCase()}` : KIND_LABEL[kind]}</span>
    {#if annot}
      <span class="page">p. {annot.page + 1}</span>
    {/if}
  </div>

  {#if annot?.quote}
    <p class="quote">“{annot.quote}”</p>
  {/if}

  <div class="colors">
    {#each COLORS as c}
      <button
        class="dot"
        class:on={color === c.value}
        style="--c:{c.value}"
        title={c.name}
        onclick={() => recolor(c.value)}
      ></button>
    {/each}
    {#if kind === "freetext"}
      <button class="dot" class:on={color === "#1d1d1f"} style="--c:#1d1d1f" title="Black" onclick={() => recolor("#1d1d1f")}
      ></button>
    {/if}
  </div>

  <textarea
    bind:this={field}
    bind:value={text}
    onkeydown={onKey}
    rows={kind === "freetext" || kind === "note" ? 3 : 2}
    placeholder={bodyLabel === "Comment" ? "Add a comment…" : "Type here…"}
    spellcheck="false"
  ></textarea>

  <div class="actions">
    {#if annot}
      <button class="icon danger" title="Delete" onclick={remove}><Icon name="trash" size={15} /></button>
      {#if markup}
        <button class="text-btn" onclick={toNote}>
          <Icon name="mdnote" size={14} />
          {hasPin ? "Show in Note" : "Note in MD"}
        </button>
      {/if}
    {/if}
    <span class="grow"></span>
    {#if placing}
      <button class="text-btn" onclick={onclose}>Cancel</button>
    {/if}
    <button class="primary" onclick={commit}>{placing ? "Add" : "Done"}</button>
  </div>
</Popover>

<style>
  .head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 2px 4px 6px;
  }

  .kind {
    font-weight: 600;
  }

  .page {
    font-size: 11px;
    color: var(--secondary);
  }

  .quote {
    margin: 0 4px 8px;
    font-size: 12px;
    font-style: italic;
    color: var(--secondary);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .colors {
    display: flex;
    gap: 6px;
    padding: 0 4px 8px;
  }

  .dot {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
  }

  .dot.on {
    box-shadow:
      0 0 0 2px var(--popover),
      0 0 0 4px var(--accent);
  }

  textarea {
    display: block;
    width: 100%;
    resize: vertical;
    min-height: 44px;
    padding: 6px 8px;
    border: none;
    border-radius: 7px;
    background: var(--hover);
    color: var(--text);
    font: 13px/1.4 var(--font);
    outline: none;
    user-select: text;
  }

  textarea:focus {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 4px;
    padding-top: 8px;
  }

  .grow {
    flex: 1;
  }

  .icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 26px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .icon.danger:hover {
    background: rgb(255 59 48 / 0.12);
    color: #ff3b30;
  }

  .text-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 6px;
  }

  .text-btn:hover {
    background: var(--hover);
  }

  .primary {
    padding: 3px 14px;
    border-radius: 6px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
  }
</style>
