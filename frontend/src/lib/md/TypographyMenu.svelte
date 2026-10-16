<script lang="ts">
  // "Aa" popover of the Markdown editor: font and spacing.
  import { FONTS, RANGES, reset, save, setFont, typo, type FontKey } from "./typography.svelte";

  let { onclose }: { onclose: () => void } = $props();

  const sliders = [
    { key: "size", label: "Size", format: (v: number) => `${v}px` },
    { key: "lineHeight", label: "Line spacing", format: (v: number) => v.toFixed(2) },
    { key: "letterSpacing", label: "Letter spacing", format: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}em` },
    { key: "width", label: "Text width", format: (v: number) => `${v}px` },
  ] as const;
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}></div>
<div class="menu" role="dialog" aria-label="Text settings">
  <div class="fonts">
    {#each Object.entries(FONTS) as [key, font]}
      <button
        class="font"
        class:on={typo.font === key}
        style="font-family:{font.stack}"
        onclick={() => setFont(key as FontKey)}
      >
        <span class="sample">Aa</span>
        <span class="name">{font.label}</span>
      </button>
    {/each}
  </div>

  {#each sliders as s}
    {@const range = RANGES[s.key]}
    <label class="row">
      <span class="label">{s.label}</span>
      <input
        type="range"
        min={range.min}
        max={range.max}
        step={range.step}
        bind:value={typo[s.key]}
        oninput={save}
      />
      <span class="value">{s.format(typo[s.key])}</span>
    </label>
  {/each}

  <div class="foot">
    <button class="reset" onclick={reset}>Reset</button>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 30;
  }

  .menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 8px;
    z-index: 31;
    width: 300px;
    padding: 10px;
    border-radius: 14px;
    background: var(--popover-solid);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 32px rgb(0 0 0 / 0.24);
  }

  .fonts {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 4px;
    margin-bottom: 10px;
  }

  .font {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 2px;
    border-radius: 9px;
    background: var(--hover);
  }

  .font.on {
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .sample {
    font-size: 18px;
  }

  .name {
    font: 10px/1.2 var(--font);
    color: var(--secondary);
    text-align: center;
  }

  .row {
    display: grid;
    grid-template-columns: 92px 1fr 64px;
    align-items: center;
    gap: 6px;
    margin: 4px 0;
    font-size: 12px;
  }

  .label {
    color: var(--secondary);
  }

  .value {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-size: 11px;
  }

  input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    margin-top: 6px;
  }

  .reset {
    padding: 2px 10px;
    border-radius: 8px;
    font-size: 12px;
    background: var(--hover);
  }
</style>
