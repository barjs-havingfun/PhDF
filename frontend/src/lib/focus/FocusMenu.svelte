<script lang="ts">
  // Focus pull-down: a small pomodoro and how long the chapter / book will take at your pace.
  import {
    chapterAt,
    clock,
    duration,
    pace,
    pausePomodoro,
    pomodoro,
    setFocusLength,
    startPomodoro,
    stopPomodoro,
  } from "../reading.svelte";
  import type { Tab } from "../tab.svelte";

  let { tab, onclose }: { tab: Tab | null; onclose: () => void } = $props();

  $effect(() => {
    tab?.loadOutline();
  });

  const left = $derived.by(() => {
    if (!tab) return null;
    const here = tab.page + tab.scroll;
    const chapter = chapterAt(tab.outline, tab.page, tab.pageCount);
    const chapterPages = chapter ? Math.max(chapter.end - here, 0) : null;
    const bookPages = Math.max(tab.pageCount - here, 0);
    return {
      chapter: chapter && { title: chapter.title, pages: chapterPages!, seconds: chapterPages! * pace.secondsPerPage },
      book: { pages: bookPages, seconds: bookPages * pace.secondsPerPage },
    };
  });

  const LENGTHS = [15, 25, 45, 50];

  function pages(n: number) {
    const count = Math.ceil(n);
    return `${count} page${count === 1 ? "" : "s"}`;
  }
</script>

<div class="dropdown" role="dialog" aria-label="Focus">
  <div class="title">Pomodoro</div>
  <div class="timer">
    <span class="phase">{pomodoro.phase === "break" ? "Break" : pomodoro.phase === "focus" ? "Focus" : "Ready"}</span>
    <span class="clock" class:break={pomodoro.phase === "break"}>{clock(pomodoro.remaining)}</span>
    {#if pomodoro.rounds}<span class="rounds">{pomodoro.rounds} done</span>{/if}
  </div>
  <div class="row">
    {#if pomodoro.running}
      <button class="btn" onclick={pausePomodoro}>Pause</button>
    {:else}
      <button class="btn primary" onclick={startPomodoro}>{pomodoro.phase === "idle" ? "Start" : "Resume"}</button>
    {/if}
    <button class="btn" onclick={stopPomodoro} disabled={pomodoro.phase === "idle"}>Reset</button>
    <span class="grow"></span>
    {#each LENGTHS as min}
      <button class="chip" class:on={pomodoro.focusMin === min} onclick={() => setFocusLength(min)} title="{min} min focus">
        {min}
      </button>
    {/each}
  </div>

  <div class="sep"></div>
  <div class="title">Time left</div>
  {#if left}
    {#if left.chapter}
      <div class="stat">
        <span class="what" title={left.chapter.title}>This chapter · {left.chapter.title}</span>
        <span class="how">~{duration(left.chapter.seconds)} <small>({pages(left.chapter.pages)})</small></span>
      </div>
    {/if}
    <div class="stat">
      <span class="what">Whole document</span>
      <span class="how">~{duration(left.book.seconds)} <small>({pages(left.book.pages)})</small></span>
    </div>
    <p class="hint">
      Your pace: ~{duration(pace.secondsPerPage)} per page
      {pace.samples < 5 ? "· still learning it as you read" : ""}
    </p>
  {:else}
    <p class="hint">Open a PDF to see how long it will take.</p>
  {/if}
</div>

<style>
  .dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 21;
    width: 300px;
    padding: 8px;
    border-radius: 11px;
    background: var(--popover-solid);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 32px rgb(0 0 0 / 0.24);
  }

  .title {
    padding: 2px 4px 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .timer {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 0 4px 8px;
  }

  .phase {
    width: 44px;
    font-size: 12px;
    color: var(--secondary);
  }

  .clock {
    font: 600 30px/1 var(--font);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.5px;
  }

  .clock.break {
    color: #34c759;
  }

  .rounds {
    margin-left: auto;
    font-size: 11px;
    color: var(--secondary);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 4px;
  }

  .grow {
    flex: 1;
  }

  .btn {
    padding: 3px 12px;
    border-radius: 6px;
    background: var(--hover);
    font-weight: 500;
  }

  .btn.primary {
    background: var(--accent);
    color: var(--accent-text);
  }

  .btn:disabled {
    opacity: 0.4;
  }

  .chip {
    padding: 1px 7px;
    border-radius: 5px;
    font-size: 11px;
    background: var(--hover);
    font-variant-numeric: tabular-nums;
  }

  .chip.on {
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }

  .sep {
    height: 0.5px;
    margin: 10px 4px 8px;
    background: var(--separator);
  }

  .stat {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 3px 4px;
  }

  .what {
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--secondary);
  }

  .how {
    flex: none;
    font-weight: 600;
  }

  small {
    font-weight: 400;
    color: var(--secondary);
  }

  .hint {
    margin: 6px 4px 0;
    font-size: 11px;
    color: var(--tertiary);
  }
</style>
