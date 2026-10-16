<script lang="ts">
  // Read Mode pull-down: reading ruler, zen, full screen, page tint — each on its own.
  import { kbd } from "../platform";
  import Icon from "../Icon.svelte";
  import { api } from "../api";
  import { read, RULER_SIZES, saveReadSettings, TINTS, type PageLayout, type RulerSize, type Tint } from "../reading.svelte";

  interface Props {
    onclose: () => void;
    onzen: () => void;
    onfullscreen: () => void;
  }

  let { onclose, onzen, onfullscreen }: Props = $props();

  function toggleRuler() {
    read.ruler = !read.ruler;
    saveReadSettings();
  }

  function setRulerSize(size: RulerSize) {
    read.rulerSize = size;
    read.ruler = true;
    saveReadSettings();
  }

  function setTint(tint: Tint) {
    read.tint = tint;
    saveReadSettings();
  }

  function setPages(layout: PageLayout) {
    read.pages = layout;
    saveReadSettings();
  }

  /** E-books (EPUB) are laid out again with the new text size; open ones update in place. */
  async function setEpubSize(size: number) {
    read.epubSize = Math.min(28, Math.max(7, size));
    saveReadSettings();
    const changed = await (await api()).epub_text_size(read.epubSize);
    window.dispatchEvent(new CustomEvent("phdf:reflow", { detail: changed }));
  }
</script>

<div class="dropdown" role="menu">
  <div class="head">
    <div class="title">Read Mode</div>
    <button class="x" onclick={onclose} title="Close (Esc)" aria-label="Close"><Icon name="close" size={12} /></button>
  </div>

  <button class="item" role="menuitemcheckbox" aria-checked={read.ruler} onclick={toggleRuler}>
    <span class="check">{read.ruler ? "✓" : ""}</span>
    <span class="text">
      Reading ruler
      <small>Dims everything but the lines under the pointer</small>
    </span>
  </button>
  <div class="sub">
    {#each Object.keys(RULER_SIZES) as size}
      <button class="chip" class:on={read.ruler && read.rulerSize === size} onclick={() => setRulerSize(size as RulerSize)}>
        {size.toUpperCase()}
      </button>
    {/each}
  </div>

  <button class="item" role="menuitemcheckbox" aria-checked={read.zen} onclick={onzen}>
    <span class="check">{read.zen ? "✓" : ""}</span>
    <span class="text">
      Zen mode <span class="key">{kbd("Ctrl+.")}</span>
      <small>Hide toolbar, tabs and sidebar</small>
    </span>
  </button>

  <button class="item" role="menuitemcheckbox" aria-checked={read.fullscreen} onclick={onfullscreen}>
    <span class="check">{read.fullscreen ? "✓" : ""}</span>
    <span class="text">Full screen <span class="key">F11</span></span>
  </button>

  <div class="sep"></div>
  <button class="book-btn" class:on={read.book} onclick={() => ((read.book = !read.book), onclose())}>
    <span class="book-ico"><i></i><i></i></span>
    <span>
      {read.book ? "Close book view" : "Read like a book"}
      <small>{read.book ? "Back to the normal view, at the same page" : "Two pages at a time, turn with ← / →"}</small>
    </span>
  </button>

  <div class="label">Pages</div>
  <div class="layouts">
    {#each [["single", "Single"], ["spread", "Two pages"], ["cover", "Cover alone"]] as [key, label]}
      <button class="layout" class:on={read.pages === key} onclick={() => setPages(key as PageLayout)} aria-pressed={read.pages === key}>
        <!-- a small drawing of the layout -->
        <span class="mini {key}">
          {#if key === "single"}<i></i>{:else if key === "spread"}<i></i><i></i>{:else}<i class="cover"></i><i></i><i></i>{/if}
        </span>
        {label}
      </button>
    {/each}
  </div>

  <div class="label">E-book text size</div>
  <div class="sub">
    <button class="chip" onclick={() => setEpubSize(read.epubSize - 1)} disabled={read.epubSize <= 7}>A−</button>
    <span class="size">{read.epubSize} pt</span>
    <button class="chip" onclick={() => setEpubSize(read.epubSize + 1)} disabled={read.epubSize >= 28}>A+</button>
  </div>

  <div class="sep"></div>
  <div class="label">Page tint</div>
  <div class="sub tints">
    {#each Object.entries(TINTS) as [key, tint]}
      <button
        class="swatch"
        class:on={read.tint === key}
        style="--c:{key === 'none' ? 'var(--surface)' : tint.color}"
        title={tint.label}
        onclick={() => setTint(key as Tint)}
      >
        {#if key === "none"}<Icon name="close" size={11} />{/if}
      </button>
    {/each}
  </div>
</div>

<style>
  .size {
    min-width: 44px;
    text-align: center;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .x {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    margin-right: 2px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .x:hover {
    background: var(--hover);
    color: var(--text);
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 21;
    width: 270px;
    padding: 6px;
    border-radius: 14px;
    background: var(--popover-solid);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 32px rgb(0 0 0 / 0.24);
  }

  .title,
  .label {
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    color: var(--secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .item {
    display: flex;
    gap: 6px;
    width: 100%;
    padding: 5px 8px;
    border-radius: 8px;
    text-align: left;
  }

  .item:hover {
    background: var(--hover);
  }

  .check {
    flex: none;
    width: 14px;
    color: var(--accent);
    font-weight: 700;
  }

  .text {
    display: flex;
    flex-direction: column;
  }

  small {
    font-size: 11px;
    color: var(--secondary);
  }

  .key {
    margin-left: 6px;
    font-size: 11px;
    color: var(--tertiary);
  }

  .sub {
    display: flex;
    gap: 4px;
    padding: 2px 8px 6px 28px;
  }

  .book-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    width: calc(100% - 8px);
    margin: 2px 4px 8px;
    padding: 8px 10px;
    border-radius: 10px;
    text-align: left;
    font-weight: 600;
    color: white;
    background: linear-gradient(135deg, #2557c9, #4b2bb8); /* dark enough for white text */
    box-shadow: 0 4px 14px rgb(94 155 255 / 0.3);
  }

  .book-btn small {
    display: block;
    font-weight: 400;
    font-size: 11px;
    opacity: 0.85;
  }

  .book-btn:hover {
    filter: brightness(1.08);
  }

  .book-ico {
    display: flex;
    gap: 2px;
  }

  .book-ico i {
    width: 11px;
    height: 15px;
    border-radius: 1px;
    background: white;
  }

  .layouts {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    padding: 2px 4px 6px;
  }

  .layout {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    padding: 8px 4px 6px;
    border-radius: 9px;
    font-size: 11px;
    background: var(--hover);
    color: var(--secondary);
    transition: background 0.12s, color 0.12s;
  }

  .layout:hover {
    color: var(--text);
  }

  .layout.on {
    background: color-mix(in srgb, var(--accent) 16%, transparent);
    color: var(--accent);
    box-shadow: inset 0 0 0 1.5px var(--accent);
    font-weight: 600;
  }

  .mini {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 22px;
  }

  .mini i {
    width: 13px;
    height: 18px;
    border-radius: 1px;
    background: currentColor;
    opacity: 0.55;
  }

  .mini.cover i.cover {
    margin-right: 4px;
  }

  .layout.on .mini i {
    opacity: 0.9;
  }

  .chip {
    padding: 1px 9px;
    border-radius: 6px;
    font-size: 11px;
    background: var(--hover);
  }

  .chip.on {
    background: var(--accent);
    color: var(--accent-text);
  }

  .sep {
    height: 0.5px;
    margin: 4px 6px;
    background: var(--separator);
  }

  .tints {
    padding-left: 8px;
  }

  .swatch {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--c);
    color: var(--secondary);
    box-shadow: inset 0 0 0 1px var(--separator);
  }

  .swatch.on {
    box-shadow:
      0 0 0 2px var(--popover),
      0 0 0 4px var(--accent);
  }
</style>
