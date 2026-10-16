<script lang="ts">
  // Bottom bar of grading mode: Prev · n / N · [grade] · Done, the Automated switch and CSV.
  import Icon from "../Icon.svelte";
  import { grading, setAutomated, type GradingSession } from "./grading.svelte";

  let { session }: { session: GradingSession } = $props();

  let gradeInput = $state<HTMLInputElement>();
  const exam = $derived(session.exam);

  // After the drawer is confirmed, go straight to the grade.
  $effect(() => {
    if (!session.drawer && grading.automated && !session.busy) gradeInput?.focus();
  });

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      session.next();
    }
  }
</script>

<div class="bar" role="toolbar" aria-label="Grading">
  <button class="nav" onclick={() => session.prev()} disabled={session.index === 0 || session.busy} title="Previous exam">
    <Icon name="left" size={15} /> Prev
  </button>

  <div class="where" title={exam?.rel}>
    <span class="count">{session.index + 1} / {session.exams.length}</span>
    <span class="who">{grading.automated ? session.ident || exam?.name : exam?.name}</span>
    {#if exam && session.isDone(exam)}<span class="done-mark"><Icon name="check" size={12} /></span>{/if}
  </div>

  {#if grading.automated}
    <label class="grade">
      Grade
      <input
        bind:this={gradeInput}
        bind:value={session.grade}
        onkeydown={onKey}
        placeholder="-"
        spellcheck="false"
        aria-label="Grade"
      />
    </label>
  {/if}

  <button class="done" onclick={() => session.next()} disabled={session.busy} title="Save and open the next exam (Enter in the grade box)">
    Done <Icon name="right" size={15} />
  </button>

  <span class="sep"></span>

  <label class="auto" title="Ask who wrote each exam and type the grade here; both go into the table">
    <input type="checkbox" checked={grading.automated} onchange={(e) => setAutomated((e.currentTarget as HTMLInputElement).checked)} />
    Automated
  </label>
  {#if grading.automated && !session.drawer}
    <button class="small" onclick={() => (session.drawer = true)} title="Change the identification">ID</button>
  {/if}
  <button class="small" onclick={() => session.exportCsv()} title="Export the grades table as CSV">CSV</button>
</div>

<style>
  .bar {
    position: absolute;
    left: 50%;
    bottom: 16px;
    transform: translateX(-50%);
    z-index: 8;
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: calc(100% - 24px);
    padding: 6px 8px;
    border-radius: 18px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 8px 28px rgb(0 0 0 / 0.22);
    font-size: 12.5px;
    white-space: nowrap;
  }

  button {
    display: flex;
    align-items: center;
    gap: 3px;
    border-radius: 10px;
  }

  .nav {
    padding: 5px 10px 5px 6px;
    background: var(--hover);
  }

  .done {
    padding: 5px 6px 5px 12px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 600;
  }

  button:disabled {
    opacity: 0.45;
  }

  .where {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    max-width: 220px;
  }

  .count {
    color: var(--secondary);
    font-variant-numeric: tabular-nums;
  }

  .who {
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
  }

  .done-mark {
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #34c759;
    color: white;
  }

  .grade {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--secondary);
  }

  .grade input {
    width: 64px;
    padding: 4px 8px;
    border: none;
    border-radius: 9px;
    background: var(--hover);
    box-shadow: inset 0 0 0 1px var(--separator);
    color: var(--text);
    font: 600 14px var(--font);
    text-align: center;
    outline: none;
    user-select: text;
  }

  .grade input:focus {
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .sep {
    width: 0.5px;
    height: 20px;
    background: var(--separator);
  }

  .auto {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--secondary);
  }

  .small {
    padding: 3px 8px;
    color: var(--secondary);
    font-size: 11.5px;
  }

  .small:hover {
    background: var(--hover);
    color: var(--text);
  }
</style>
