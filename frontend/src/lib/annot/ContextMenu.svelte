<script lang="ts">
  // Right-click menu on a PDF page: on an annotation (edit, colour, copy, note pin, delete) or on
  // an empty spot (add a note / text there, bookmark, copy the page as an image, ask the AI,
  // park a thought). Right-click on selected text shows the selection menu instead (Viewer).
  import { kbd, copyText } from "../platform";
  import { api, pageImageUrl } from "../api";
  import { askAi } from "../ai/terminal.svelte";
  import { notify } from "../notify.svelte";
  import type { Tab } from "../tab.svelte";
  import type { ContextTarget } from "../viewer/Viewer.svelte";
  import { COLORS } from "./colors";

  interface Props {
    tab: Tab;
    target: ContextTarget;
    x: number; // screen position of the click
    y: number;
    paneId: number | null;
    onedit: () => void; // open the annotation editor
    onplace?: (kind: "note" | "freetext") => void; // missing: no "Add … Here" items
    onpark?: () => void;
    onclose: () => void;
  }

  let { tab, target, x, y, paneId, onedit, onplace, onpark, onclose }: Props = $props();

  let menu = $state<HTMLDivElement>();
  // Keep the menu on screen.
  const pos = $derived.by(() => {
    const w = menu?.offsetWidth ?? 220;
    const h = menu?.offsetHeight ?? 240;
    return `left:${Math.min(x, innerWidth - w - 8)}px;top:${Math.min(y, innerHeight - h - 8)}px`;
  });

  const annot = $derived(target.kind === "annot" ? target.annot : null);
  const page = $derived(target.kind === "annot" ? target.annot.page : target.page);
  // A highlight's words, or a note's / text box's text; a highlight's comment separately.
  const text = $derived(annot ? annot.quote || (annot.kind === "ink" ? "" : annot.contents.trim()) : "");
  const comment = $derived(annot?.quote ? annot.contents.trim() : "");

  /** Start the action (it may still need the menu's target), then close. */
  function run(action: () => unknown) {
    let result: unknown;
    try {
      result = action();
    } finally {
      onclose();
    }
    Promise.resolve(result).catch((e) => notify.error(String(e)));
  }

  async function notePin() {
    if (!annot) return;
    if (tab.hasPin(annot.id)) {
      await tab.toggleMd(true);
      tab.mdView = "note";
      tab.mdReveal = { id: annot.id, nonce: Date.now() };
    } else await tab.noteInMd(annot);
  }

  async function bookmark() {
    const on = await tab.toggleBookmark(page);
    notify.show({ text: on ? `Page ${page + 1} bookmarked.` : `Bookmark on page ${page + 1} removed.` }, 1800);
  }

  /** The page as a PNG on the clipboard (photo pages come as JPEG and are converted). */
  async function copyPage() {
    const [w] = tab.doc.pageSizes[page];
    const url = pageImageUrl(tab.doc.docId, page, Math.min(3, 1800 / w), undefined, tab.revs[page] ?? 0);
    let blob = await (await fetch(url)).blob();
    if (blob.type !== "image/png") {
      const bmp = await createImageBitmap(blob);
      const canvas = document.createElement("canvas");
      canvas.width = bmp.width;
      canvas.height = bmp.height;
      canvas.getContext("2d")!.drawImage(bmp, 0, 0);
      blob = await new Promise<Blob>((ok, fail) => canvas.toBlob((b) => (b ? ok(b) : fail("no image")), "image/png"));
    }
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    notify.show({ text: `Page ${page + 1} copied as an image.` }, 1800);
  }

  /** Like "My own question…": the page's text and where it is from, without pressing Enter. */
  async function askPage() {
    const ctx = await (await api()).ai_context(tab.doc.docId, page, page);
    const prompt =
      `Read the file "${ctx.path}". It is the text of page ${page + 1} (“${tab.title}”), converted to ` +
      `Markdown from the PDF "${tab.path}".\n\n`;
    await askAi(prompt, false, tab.path.replace(/[\\/][^\\/]*$/, ""), paneId);
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose} oncontextmenu={(e) => (e.preventDefault(), onclose())}></div>
<div class="menu" role="menu" bind:this={menu} style={pos}>
  {#if annot}
    <button role="menuitem" onclick={() => run(onedit)}>Edit…</button>
    <div class="colors">
      {#each COLORS as c}
        <button
          class="dot"
          class:on={annot.color === c.value}
          style="--c:{c.value}"
          title={c.name}
          aria-label="Colour {c.name}"
          onclick={() => run(() => tab.updateAnnotation(annot.id, c.value))}
        ></button>
      {/each}
    </div>
    {#if text}
      <button role="menuitem" onclick={() => run(() => copyText(text))}>Copy Text</button>
    {/if}
    {#if comment}
      <button role="menuitem" onclick={() => run(() => copyText(comment))}>Copy Comment</button>
    {/if}
    <button role="menuitem" onclick={() => run(notePin)}>{tab.hasPin(annot.id) ? "Go to Pin in Note" : "Note in MD"}</button>
    <div class="sep"></div>
    <button role="menuitem" class="danger" onclick={() => run(() => tab.deleteAnnotation(annot.id))}>
      Delete <span class="shortcut">Del</span>
    </button>
  {:else}
    {#if onplace}
      <button role="menuitem" onclick={() => run(() => onplace("note"))}>Add Note Here</button>
      <button role="menuitem" onclick={() => run(() => onplace("freetext"))}>Add Text Here</button>
      <div class="sep"></div>
    {/if}
    <button role="menuitem" onclick={() => run(bookmark)}>
      {tab.isBookmarked(page) ? "Remove Bookmark" : "Bookmark This Page"} <span class="shortcut">{kbd("Ctrl+B")}</span>
    </button>
    <button role="menuitem" onclick={() => run(copyPage)}>Copy Page as Image</button>
    <div class="sep"></div>
    <button role="menuitem" onclick={() => run(askPage)}>Ask AI About This Page…</button>
    {#if onpark}
      <button role="menuitem" onclick={() => run(onpark)}>Park a Thought <span class="shortcut">{kbd("Ctrl+Shift+Space")}</span></button>
    {/if}
  {/if}
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 46; /* above the link preview */
  }

  .menu {
    position: fixed;
    z-index: 47;
    min-width: 210px;
    padding: 5px;
    border-radius: 12px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
  }

  button[role="menuitem"] {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    width: 100%;
    padding: 3px 10px;
    border-radius: 6px;
    text-align: left;
    white-space: nowrap;
  }

  button[role="menuitem"]:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  .danger {
    color: #ff3b30;
  }

  .shortcut {
    color: var(--tertiary);
  }

  button:hover .shortcut {
    color: inherit;
  }

  .colors {
    display: flex;
    gap: 6px;
    padding: 4px 10px;
  }

  .dot {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
  }

  .dot:hover {
    transform: scale(1.15);
  }

  .dot.on {
    box-shadow:
      inset 0 0 0 1px rgb(0 0 0 / 0.12),
      0 0 0 2px var(--accent);
  }

  .sep {
    height: 0.5px;
    margin: 4px 6px;
    background: var(--separator);
  }
</style>
