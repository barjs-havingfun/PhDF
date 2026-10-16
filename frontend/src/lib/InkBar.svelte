<script lang="ts">
  // Pen colour and width, shown while the draw tool is on.
  import { COLORS } from "./annot/colors";
  import { INK_WIDTHS, ink, saveInk } from "./tab.svelte";

  let { topInset }: { topInset: number } = $props();

  const colors = [...COLORS.map((c) => c.value), "#1d1d1f"];
</script>

<div class="inkbar" style="top:{topInset + 10}px" role="toolbar" aria-label="Pen">
  {#each colors as c}
    <button class="dot" class:on={ink.color === c} style="--c:{c}" aria-label="Colour {c}" onclick={() => ((ink.color = c), saveInk())}></button>
  {/each}
  <span class="sep"></span>
  {#each INK_WIDTHS as w}
    <button class="width" class:on={ink.width === w} title="{w} pt" onclick={() => ((ink.width = w), saveInk())}>
      <span style="height:{Math.max(1.5, w)}px;background:{ink.color}"></span>
    </button>
  {/each}
  <span class="hint">Esc to stop drawing</span>
</div>

<style>
  .inkbar {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    z-index: 8;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 16px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 6px 20px rgb(0 0 0 / 0.18);
  }

  .dot {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--c);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.15);
  }

  .dot.on {
    box-shadow:
      0 0 0 2px var(--popover-solid),
      0 0 0 4px var(--accent);
  }

  .sep {
    width: 0.5px;
    height: 18px;
    margin: 0 4px;
    background: var(--separator);
  }

  .width {
    display: grid;
    place-items: center;
    width: 30px;
    height: 24px;
    border-radius: 8px;
  }

  .width span {
    display: block;
    width: 18px;
    border-radius: 5px;
  }

  .width.on,
  .width:hover {
    background: var(--hover);
  }

  .hint {
    margin-left: 6px;
    font-size: 11px;
    color: var(--tertiary);
  }
</style>
