<script lang="ts" module>
  import type { PdfLink } from "./api";
  import type { Tab } from "./tab.svelte";

  export interface Peek {
    tab: Tab;
    link: PdfLink;
    x: number; // anchor point in window coordinates
    y: number;
  }
</script>

<script lang="ts">
  // Link preview (R11): links open small first. Internal links show a clip of the target
  // page; web links open in a small floating window. From here: enlarge, open, or close.
  import { kbd, copyText } from "./platform";
  import { onMount } from "svelte";
  import { api } from "./api";
  import Icon from "./Icon.svelte";
  import PeekPage from "./PeekPage.svelte";

  interface Props {
    peek: Peek;
    invert: boolean;
    onclose: () => void;
    onsplit: (tab: Tab, page: number, y: number | null) => void; // open the target in a pane beside
  }

  let { peek, invert, onclose, onsplit }: Props = $props();

  function openSplit() {
    onsplit(peek.tab, target, link.y);
    close();
  }

  const CARD_WIDTH = 420;

  let expanded = $state(false);
  let selectMode = $state(false);
  let zoom = $state(1);
  let pageView = $state<PeekPage>();
  let webOpen = $state(false);
  let card = $state<HTMLElement>();

  const link = $derived(peek.link);
  const target = $derived(link.kind === "goto" ? link.page : -1);
  const startY = $derived(Math.max((link.y ?? 0) - 20, 0));

  const host = $derived.by(() => {
    try {
      return new URL(link.uri ?? "").host;
    } catch {
      return link.uri ?? "";
    }
  });

  // Place the card below the click, flipped/clamped to stay on screen.
  const position = $derived.by(() => {
    const w = CARD_WIDTH;
    const h = card?.offsetHeight ?? 300;
    const left = Math.min(Math.max(peek.x - w / 2, 12), innerWidth - w - 12);
    const below = peek.y + 14;
    const top = below + h < innerHeight - 12 ? below : peek.y - h - 14;
    return `left:${left}px;top:${Math.min(Math.max(top, 12), innerHeight - h - 12)}px`;
  });

  function goThere() {
    peek.tab.navigate({ page: target, y: link.y });
    close();
  }

  async function openWeb() {
    webOpen = await (await api()).peek_url(link.uri!);
  }

  async function enlargeWeb() {
    (await api()).peek_expand();
  }

  async function openInBrowser() {
    (await api()).open_external(link.uri!);
    close();
  }

  async function close() {
    if (webOpen) (await api()).peek_close();
    onclose();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      if (expanded) expanded = false;
      else close();
    } else if ((e.ctrlKey || e.metaKey) && (e.key === "=" || e.key === "+" || e.key === "-")) {
      // Zoom the preview, not the document behind it.
      e.preventDefault();
      e.stopImmediatePropagation();
      pageView?.zoomBy(e.key === "-" ? 1 / 1.2 : 1.2);
    }
  }

  onMount(() => {
    // Web links start small right away, as asked for in the notes.
    if (link.kind === "uri") openWeb();
  });
</script>

<svelte:window onkeydowncapture={onKeydown} />

{#snippet pageTools()}
  <div class="zoom">
    <button class="icon-btn" title={kbd("Zoom out (Ctrl+-)")} onclick={() => pageView?.zoomBy(1 / 1.2)}>
      <Icon name="minus" size={13} />
    </button>
    <span class="pct">{Math.round(zoom * 100)}%</span>
    <button class="icon-btn" title={kbd("Zoom in (Ctrl++ or Ctrl+wheel)")} onclick={() => pageView?.zoomBy(1.2)}>
      <Icon name="plus" size={13} />
    </button>
  </div>
  <button
    class="icon-btn"
    class:on={selectMode}
    title={selectMode ? kbd("Select text (Ctrl+C to copy) — click for pan mode") : "Pan — click to select text"}
    onclick={() => (selectMode = !selectMode)}
  >
    <Icon name="text" size={14} />
  </button>
{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" class:dim={expanded} onclick={close}></div>

{#if expanded && target >= 0}
  <div class="sheet" role="dialog" aria-label="Page {target + 1} preview">
    <header>
      <span class="title">Page {target + 1}</span>
      {@render pageTools()}
      <button class="text-btn" onclick={() => (expanded = false)}>Smaller</button>
      <button class="text-btn" onclick={openSplit}>Open Beside</button>
      <button class="primary" onclick={goThere}>Go to Page</button>
      <button class="icon-btn" onclick={close} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>
    <PeekPage bind:this={pageView} bind:zoom tab={peek.tab} page={target} {startY} {invert} {selectMode} />
  </div>
{:else}
  <div class="card" bind:this={card} style={position} role="dialog" aria-label="Link preview">
    {#if target >= 0}
      <header>
        <span class="title">Page {target + 1}</span>
        {@render pageTools()}
        <button class="icon-btn" onclick={() => (expanded = true)} title="Enlarge">
          <Icon name="expand" size={14} />
        </button>
        <button class="icon-btn" onclick={close} aria-label="Close"><Icon name="close" size={14} /></button>
      </header>
      <div class="clip">
        <PeekPage bind:this={pageView} bind:zoom tab={peek.tab} page={target} {startY} {invert} {selectMode} />
      </div>
      <footer>
        <button class="text-btn" onclick={() => (expanded = true)}>Enlarge</button>
        <button class="text-btn" onclick={openSplit} title="Open the target page in a pane beside this one">Open Beside</button>
        <button class="primary" onclick={goThere}>Go to Page</button>
      </footer>
    {:else}
      <header>
        <span class="title web"><Icon name="globe" size={14} /> {host}</span>
        <button class="icon-btn" onclick={close} aria-label="Close"><Icon name="close" size={14} /></button>
      </header>
      <p class="url">{link.uri}</p>
      <p class="hint">
        {webOpen ? "Opened in a small preview window." : "Opening a small preview window…"}
      </p>
      <footer>
        <button class="text-btn" onclick={() => copyText(link.uri!)}>Copy Link</button>
        <button class="text-btn" onclick={enlargeWeb} disabled={!webOpen}>Enlarge</button>
        <button class="primary" onclick={openInBrowser}>Open in Browser</button>
      </footer>
    {/if}
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
  }

  .backdrop.dim {
    background: rgb(0 0 0 / 0.35);
  }

  .card,
  .sheet {
    position: fixed;
    z-index: 41;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(24px);
    border-radius: 12px;
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 12px 40px rgb(0 0 0 / 0.25);
    overflow: hidden;
  }

  .card {
    width: 420px;
    animation: pop 0.14s ease-out;
  }

  .sheet {
    inset: 5vh 50% auto auto;
    transform: translateX(50%);
    width: min(900px, 92vw);
    height: 90vh;
    display: flex;
    flex-direction: column;
  }

  @keyframes pop {
    from {
      opacity: 0;
      transform: scale(0.96);
    }
  }

  header,
  footer {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 10px;
  }

  footer {
    justify-content: flex-end;
  }

  .title {
    flex: 1;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .clip {
    display: flex;
    height: 300px;
    border-block: 0.5px solid var(--separator);
  }

  .clip :global(.peek-page),
  .sheet :global(.peek-page) {
    flex: 1;
  }

  .zoom {
    display: flex;
    align-items: center;
    border-radius: 6px;
    background: var(--hover);
  }

  .pct {
    min-width: 40px;
    text-align: center;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .icon-btn.on {
    background: var(--pressed);
    color: var(--text);
  }

  .url {
    margin: 0 12px;
    font-size: 12px;
    color: var(--secondary);
    word-break: break-all;
    user-select: text;
  }

  .hint {
    margin: 6px 12px 0;
    font-size: 11px;
    color: var(--tertiary);
  }

  .icon-btn {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .icon-btn:hover,
  .text-btn:hover:not(:disabled) {
    background: var(--hover);
    color: var(--text);
  }

  .text-btn {
    padding: 3px 10px;
    border-radius: 6px;
  }

  .text-btn:disabled {
    opacity: 0.4;
  }

  .primary {
    padding: 3px 12px;
    border-radius: 6px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
  }
</style>
