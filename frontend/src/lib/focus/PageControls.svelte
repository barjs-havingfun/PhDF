<script lang="ts">
  // Book view's controls at the bottom right: the left / right page buttons and a zoom slider
  // above them; once zoomed, a Reset button pops out above. They turn faint while the pointer
  // rests and come back when it moves.
  import { backOut } from "svelte/easing";
  import { scale } from "svelte/transition";
  import Icon from "../Icon.svelte";
  import { ui } from "../notify.svelte";

  interface Turn {
    label: string;
    disabled: boolean;
    go: () => void;
  }

  interface Props {
    zoom: number; // 1 = the spread fits the window
    min: number;
    max: number;
    onzoom: (zoom: number) => void;
    left: Turn;
    right: Turn;
  }

  let { zoom, min, max, onzoom, left, right }: Props = $props();

  const IDLE_MS = 2500;
  let awake = $state(true);
  let over = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  function wake() {
    awake = true;
    clearTimeout(timer);
    timer = setTimeout(() => (awake = false), IDLE_MS);
  }

  $effect(() => {
    wake();
    return () => clearTimeout(timer);
  });
</script>

<svelte:window onpointermove={wake} onkeydown={wake} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="controls" class:asleep={!awake && !over} onpointerenter={() => (over = true)} onpointerleave={() => (over = false)}>
  {#if Math.abs(zoom - 1) > 0.005}
    <button
      class="reset"
      onclick={() => onzoom(1)}
      title="Back to the whole spread (Ctrl+0)"
      transition:scale={{ start: 0.4, duration: ui.reduceMotion ? 0 : 260, easing: backOut }}
    >
      <Icon name="restart" size={13} /> Reset
    </button>
  {/if}
  <div class="zoom">
    <span class="pct">{Math.round(zoom * 100)}%</span>
    <!-- a log scale: the same drag takes 50 % to 100 % and 100 % to 200 % -->
    <input
      type="range"
      min={Math.log(min)}
      max={Math.log(max)}
      step="0.01"
      value={Math.log(zoom)}
      oninput={(e) => onzoom(Math.exp(Number(e.currentTarget.value)))}
      ondblclick={() => onzoom(1)}
      aria-label="Zoom"
      title="Drag up to zoom in, down to zoom out (double-click: fit)"
    />
  </div>
  <div class="turns">
    {#each [["left", left], ["right", right]] as const as [icon, turn]}
      <button onclick={turn.go} disabled={turn.disabled} aria-label={turn.label} title={turn.label}>
        <Icon name={icon} size={18} />
      </button>
    {/each}
  </div>
</div>

<style>
  .controls {
    position: absolute;
    right: 22px;
    bottom: 18px;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    transition: opacity 0.4s;
  }

  .controls.asleep {
    opacity: 0.3;
  }

  .reset {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 12px;
    background: var(--accent);
    color: var(--accent-text);
    font-size: 11.5px;
    font-weight: 500;
    box-shadow: 0 6px 18px rgb(0 0 0 / 0.2);
  }

  .reset:hover {
    filter: brightness(1.08);
  }

  .zoom,
  .turns {
    display: flex;
    align-items: center;
    padding: 6px;
    border-radius: 14px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 6px 18px rgb(0 0 0 / 0.18);
  }

  .zoom {
    flex-direction: column;
    gap: 6px;
    padding: 8px 6px;
  }

  .pct {
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    color: var(--secondary);
  }

  /* Vertical: up zooms in. */
  input {
    writing-mode: vertical-lr;
    direction: rtl;
    width: 18px;
    height: 130px;
    margin: 0;
    accent-color: var(--accent);
    cursor: ns-resize;
  }

  .turns {
    gap: 4px;
  }

  .turns button {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    color: var(--text);
  }

  .turns button:hover:not(:disabled) {
    background: var(--hover);
  }

  .turns button:disabled {
    opacity: 0.35;
  }
</style>
