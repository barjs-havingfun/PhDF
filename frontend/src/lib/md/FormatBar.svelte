<script lang="ts" module>
  export type BarSide = "top" | "bottom" | "left" | "right";
</script>

<script lang="ts">
  // The note's format bar: inline marks, link, paragraph style, lists, insert, clipboard. Its grip
  // drags it to any side of the note (the side nearest the pointer), remembered by MdEditor.
  import type { EditorView } from "@codemirror/view";
  import { kbd } from "../platform";
  import Icon from "../Icon.svelte";
  import { capture } from "../dnd.svelte";
  import * as f from "./format";
  import { BLOCKS, INLINE, INSERTS, type Block, type Inline, type Insert } from "./format";

  interface Props {
    view: () => EditorView | undefined;
    block: Block; // paragraph style at the cursor
    side: BarSide;
    container: () => HTMLElement | undefined; // the note area the bar docks around
    onside: (side: BarSide, done: boolean) => void;
  }

  let { view, block, side, container, onside }: Props = $props();

  const ICON: Record<Inline, string> = {
    bold: "bold",
    italic: "italic",
    strike: "strike",
    highlight: "highlighter",
    code: "code",
    math: "sigma",
    comment: "comment",
  };

  let menu = $state<{ kind: "block" | "insert" | "edit"; x: number; y: number } | null>(null);
  const vertical = $derived(side === "left" || side === "right");

  function open(kind: "block" | "insert" | "edit", e: MouseEvent) {
    if (menu?.kind === kind) return (menu = null);
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    menu = vertical
      ? { kind, x: side === "left" ? r.right + 6 : r.left - 6, y: r.top }
      : { kind, x: r.left, y: side === "top" ? r.bottom + 6 : r.top - 6 };
  }

  const menuStyle = $derived.by(() => {
    if (!menu) return "";
    const x = side === "right" ? `right:${innerWidth - menu.x}px` : `left:${Math.min(menu.x, innerWidth - 220)}px`;
    const y = side === "bottom" ? `bottom:${innerHeight - menu.y}px` : `top:${Math.min(menu.y, innerHeight - 360)}px`;
    return `${x};${y}`;
  });

  function act(run: (v: EditorView) => unknown) {
    menu = null;
    const v = view();
    if (v) run(v);
  }

  const tip = (label: string, key?: string) => (key ? kbd(`${label} (${key})`) : label);
  const keep = (e: MouseEvent) => e.preventDefault(); // buttons don't take the focus from the text

  const blockLabel = $derived(block === "body" ? "Text" : block.startsWith("h") ? `Heading ${block[1]}` : BLOCKS[block]);

  // Drag the grip: the bar follows to the side of the note nearest the pointer.
  function onGrip(e: PointerEvent) {
    const el = e.currentTarget as HTMLElement;
    capture(el, e.pointerId);
    const move = (ev: PointerEvent) => {
      const box = container()?.getBoundingClientRect();
      if (!box) return;
      const d = {
        top: ev.clientY - box.top,
        bottom: box.bottom - ev.clientY,
        left: ev.clientX - box.left,
        right: box.right - ev.clientX,
      };
      const nearest = (Object.keys(d) as BarSide[]).reduce((a, b) => (d[b] < d[a] ? b : a));
      if (nearest !== side) onside(nearest, false);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      onside(side, true);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }
</script>

<div class="fbar" class:vertical role="toolbar" aria-label="Format">
  <span class="grip" role="button" tabindex="-1" aria-label="Move the format bar" title="Drag to put this bar on another side" onpointerdown={onGrip}>
    <Icon name="grip" size={16} />
  </span>

  <button class="style" title="Paragraph style: text, headings, quote, lists" onmousedown={keep} onclick={(e) => open("block", e)}>
    <Icon name="heading" size={17} /><span class="label">{blockLabel}</span><Icon name="down" size={12} />
  </button>

  <div class="group">
    {#each Object.entries(INLINE) as [kind, m]}
      <button class="b" title={tip(m.label, m.key)} aria-label={m.label} onmousedown={keep} onclick={() => act((v) => f.toggleInline(v, kind as Inline))}>
        <Icon name={ICON[kind as Inline] as never} size={18} />
      </button>
    {/each}
    <button class="b" title={tip("Link", "Ctrl+Shift+K")} aria-label="Link" onmousedown={keep} onclick={() => act(f.insertLink)}>
      <Icon name="link" size={18} />
    </button>
    <button class="b" title="Clear formatting" aria-label="Clear formatting" onmousedown={keep} onclick={() => act(f.clearFormatting)}>
      <Icon name="eraser" size={18} />
    </button>
  </div>

  <div class="group">
    <button class="b" class:on={block === "bullet"} title="Bullet list" aria-label="Bullet list" onmousedown={keep} onclick={() => act((v) => f.setBlock(v, block === "bullet" ? "body" : "bullet"))}>
      <Icon name="listBullet" size={18} />
    </button>
    <button class="b" class:on={block === "numbered"} title="Numbered list" aria-label="Numbered list" onmousedown={keep} onclick={() => act((v) => f.setBlock(v, block === "numbered" ? "body" : "numbered"))}>
      <Icon name="listNumber" size={18} />
    </button>
    <button class="b" class:on={block === "task"} title="Task list (checkboxes)" aria-label="Task list" onmousedown={keep} onclick={() => act((v) => f.setBlock(v, block === "task" ? "body" : "task"))}>
      <Icon name="listTask" size={18} />
    </button>
    <button class="b" class:on={block === "quote"} title="Quote" aria-label="Quote" onmousedown={keep} onclick={() => act((v) => f.setBlock(v, block === "quote" ? "body" : "quote"))}>
      <Icon name="quote" size={18} />
    </button>
  </div>

  <div class="group">
    <button class="b wide" title="Insert a table, callout, footnote, code or math block, line" onmousedown={keep} onclick={(e) => open("insert", e)}>
      <Icon name="plus" size={17} /><span class="label">Insert</span>
    </button>
    <button class="b" title="Cut, copy, paste" aria-label="Clipboard" onmousedown={keep} onclick={(e) => open("edit", e)}>
      <Icon name="clipboard" size={18} />
    </button>
  </div>
</div>

{#if menu}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="backdrop" onclick={() => (menu = null)}></div>
  <div class="menu" role="menu" style={menuStyle}>
    {#if menu.kind === "block"}
      {#each Object.entries(BLOCKS) as [kind, label]}
        <button role="menuitemradio" aria-checked={block === kind} class="blk {kind}" onmousedown={keep} onclick={() => act((v) => f.setBlock(v, kind as Block))}>
          {kind === "body" ? "Text" : label}
        </button>
      {/each}
    {:else if menu.kind === "insert"}
      {#each Object.entries(INSERTS) as [kind, label]}
        <button role="menuitem" onmousedown={keep} onclick={() => act((v) => f.insertBlock(v, kind as Insert))}>{label}</button>
      {/each}
    {:else}
      <button role="menuitem" onmousedown={keep} onclick={() => act(f.cut)}>Cut <span class="key">{kbd("Ctrl+X")}</span></button>
      <button role="menuitem" onmousedown={keep} onclick={() => act(f.copy)}>Copy <span class="key">{kbd("Ctrl+C")}</span></button>
      <button role="menuitem" onmousedown={keep} onclick={() => act((v) => f.paste(v))}>Paste <span class="key">{kbd("Ctrl+V")}</span></button>
      <button role="menuitem" onmousedown={keep} onclick={() => act((v) => f.paste(v, true))}>Paste as Plain Text</button>
    {/if}
  </div>
{/if}

<style>
  .fbar {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    overflow: auto;
    scrollbar-width: none;
    border-bottom: 0.5px solid var(--separator);
    background: var(--toolbar);
  }

  .fbar.vertical {
    flex-direction: column;
    padding: 8px 5px;
    border-bottom: none;
  }

  .group {
    flex: none;
    display: flex;
    align-items: center;
    gap: 1px;
    padding: 2px;
    border-radius: 12px;
    background: var(--hover);
  }

  .vertical .group {
    flex-direction: column;
  }

  .grip {
    flex: none;
    display: grid;
    place-items: center;
    width: 18px;
    color: var(--tertiary);
    cursor: grab;
    user-select: none;
    touch-action: none;
  }

  .grip:active {
    cursor: grabbing;
  }

  .vertical .grip {
    transform: rotate(90deg);
  }

  .b,
  .style {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-width: 32px;
    height: 30px;
    padding: 0 6px;
    border-radius: 9px;
    color: var(--secondary);
    transition:
      background 0.1s,
      color 0.1s;
  }

  .b:hover,
  .style:hover {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.08);
  }

  .b.on {
    background: var(--surface);
    color: var(--accent);
  }

  .style {
    min-width: 128px;
    justify-content: flex-start;
    padding: 0 8px;
    background: var(--hover);
    font-size: 13px;
    color: var(--text);
  }

  .style .label {
    flex: 1;
    text-align: left;
  }

  .label {
    font-size: 13px;
  }

  .vertical .style {
    min-width: 0;
  }

  .vertical .label {
    display: none;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
  }

  .menu {
    position: fixed;
    z-index: 41;
    min-width: 200px;
    padding: 6px;
    border-radius: 13px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 30px rgb(0 0 0 / 0.22);
  }

  .menu button {
    position: relative;
    display: flex;
    justify-content: space-between;
    gap: 14px;
    width: 100%;
    padding: 5px 12px 5px 26px;
    border-radius: 8px;
    text-align: left;
    font-size: 13px;
  }

  .menu button[aria-checked="true"]::before {
    content: "✓";
    position: absolute;
    left: 9px;
  }

  .menu button:hover {
    background: var(--accent);
    color: var(--accent-text);
  }

  /* The style menu previews each style. */
  .blk.h1 {
    font-size: 19px;
    font-weight: 700;
  }
  .blk.h2 {
    font-size: 17px;
    font-weight: 700;
  }
  .blk.h3 {
    font-size: 15px;
    font-weight: 650;
  }
  .blk.h4,
  .blk.h5,
  .blk.h6 {
    font-weight: 600;
  }
  .blk.quote {
    font-style: italic;
  }

  .key {
    color: var(--tertiary);
  }

  .menu button:hover .key {
    color: inherit;
  }
</style>
