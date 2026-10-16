<script lang="ts">
  // Reading stats: headline numbers + minutes read per day over the last 14 days (one series,
  // so no legend; hover a bar for its value; a table view for screen readers / exact numbers).
  import { onMount } from "svelte";
  import { api, type ReadingStats } from "../api";

  let stats = $state<ReadingStats | null>(null);
  let hover = $state<number | null>(null);
  let showTable = $state(false);

  onMount(async () => {
    stats = await (await api()).reading_stats();
  });

  function fmt(seconds: number) {
    const min = Math.round(seconds / 60);
    if (min < 60) return `${min} min`;
    return `${Math.floor(min / 60)} h ${min % 60} min`;
  }

  const W = 420;
  const H = 110;
  const PAD = { top: 10, bottom: 18, left: 0, right: 0 };
  const max = $derived(Math.max(15 * 60, ...(stats?.days.map((d) => d.seconds) ?? [0])));
  const barW = $derived(stats ? (W - PAD.left - PAD.right) / stats.days.length : 0);

  function label(day: string) {
    return new Date(day + "T12:00").toLocaleDateString(undefined, { weekday: "narrow" });
  }

  function longDate(day: string) {
    return new Date(day + "T12:00").toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  }
</script>

{#if stats}
  <section class="box">
    <h2>Reading</h2>
    <div class="tiles">
      <div class="tile"><span class="num">{fmt(stats.today)}</span><span class="cap">today</span></div>
      <div class="tile"><span class="num">{fmt(stats.week)}</span><span class="cap">this week</span></div>
      <div class="tile">
        <span class="num">{stats.streak} day{stats.streak === 1 ? "" : "s"}</span><span class="cap">streak</span>
      </div>
    </div>

    <figure>
      <figcaption>Minutes read per day — last 14 days</figcaption>
      <div class="chart">
        <svg viewBox="0 0 {W} {H}" role="img" aria-label="Minutes read per day over the last 14 days">
          <line class="base" x1="0" x2={W} y1={H - PAD.bottom} y2={H - PAD.bottom} />
          {#each stats.days as d, i}
            {@const h = ((H - PAD.top - PAD.bottom) * d.seconds) / max}
            {@const x = PAD.left + i * barW}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <g onmouseenter={() => (hover = i)} onmouseleave={() => (hover = null)}>
              <rect class="hit" x={x} y={PAD.top} width={barW} height={H - PAD.top - PAD.bottom} />
              {#if d.seconds > 0}
                <path
                  class="bar"
                  class:dim={hover !== null && hover !== i}
                  d="M{x + 2},{H - PAD.bottom} v{-Math.max(h - 4, 0)} q0,-4 4,-4 h{barW - 12} q4,0 4,4 v{Math.max(h - 4, 0)} z"
                />
              {/if}
              <text class="tick" x={x + barW / 2} y={H - 4} text-anchor="middle">{label(d.day)}</text>
            </g>
          {/each}
        </svg>
        {#if hover !== null}
          {@const d = stats.days[hover]}
          <div class="tip" style="left:{((hover + 0.5) / stats.days.length) * 100}%">
            <b>{fmt(d.seconds)}</b> · {longDate(d.day)}
          </div>
        {/if}
      </div>
      <button class="table-toggle" onclick={() => (showTable = !showTable)}>{showTable ? "Hide" : "Show"} as table</button>
      {#if showTable}
        <table>
          <tbody>
            {#each stats.days as d}
              <tr><td>{longDate(d.day)}</td><td class="r">{fmt(d.seconds)}</td></tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </figure>
    <p class="hint">Only time actually spent reading counts — not skimming, idle time or breaks.</p>
  </section>
{/if}

<style>
  .box {
    width: 100%;
    margin-top: 14px;
    padding: 12px 14px 12px;
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  h2 {
    margin: 0 0 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary);
  }

  .tiles {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .tile {
    display: flex;
    flex-direction: column;
    padding: 8px 10px;
    border-radius: 9px;
    background: var(--hover);
  }

  .num {
    font: 600 18px/1.2 var(--font);
    font-variant-numeric: tabular-nums;
  }

  .cap {
    font-size: 11px;
    color: var(--secondary);
  }

  figure {
    margin: 14px 0 0;
  }

  figcaption {
    font-size: 12px;
    color: var(--secondary);
    margin-bottom: 4px;
  }

  .chart {
    position: relative;
  }

  svg {
    display: block;
    width: 100%;
    height: auto;
  }

  .base {
    stroke: var(--separator);
    stroke-width: 1;
  }

  .hit {
    fill: transparent;
  }

  .bar {
    fill: var(--accent);
    transition: opacity 0.12s;
  }

  .bar.dim {
    opacity: 0.35;
  }

  .tick {
    font: 9px var(--font);
    fill: var(--secondary);
  }

  .tip {
    position: absolute;
    top: -6px;
    transform: translate(-50%, -100%);
    padding: 3px 8px;
    border-radius: 6px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 4px 12px rgb(0 0 0 / 0.18);
    font-size: 11px;
    white-space: nowrap;
    pointer-events: none;
  }

  .table-toggle {
    margin-top: 6px;
    font-size: 11px;
    color: var(--accent);
  }

  table {
    width: 100%;
    margin-top: 6px;
    border-collapse: collapse;
    font-size: 12px;
  }

  td {
    padding: 2px 0;
    border-bottom: 0.5px solid var(--separator);
  }

  .r {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .hint {
    margin: 8px 0 0;
    font-size: 11px;
    color: var(--tertiary);
  }
</style>
