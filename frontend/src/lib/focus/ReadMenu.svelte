<script lang="ts">
  // Read Mode pull-down: reading ruler, zen, full screen, page tint — each on its own.
  import Icon from "../Icon.svelte";
  import { read, RULER_SIZES, saveReadSettings, TINTS, type RulerSize, type Tint } from "../reading.svelte";

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
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="menu-backdrop" onclick={onclose}></div>
<div class="dropdown" role="menu">
  <div class="title">Read Mode</div>

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
      Zen mode <span class="key">Ctrl+.</span>
      <small>Hide toolbar, tabs and sidebar</small>
    </span>
  </button>

  <button class="item" role="menuitemcheckbox" aria-checked={read.fullscreen} onclick={onfullscreen}>
    <span class="check">{read.fullscreen ? "✓" : ""}</span>
    <span class="text">Full screen <span class="key">F11</span></span>
  </button>

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
  .menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: 20;
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 21;
    width: 270px;
    padding: 6px;
    border-radius: 11px;
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
    border-radius: 6px;
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

  .chip {
    padding: 1px 9px;
    border-radius: 5px;
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
