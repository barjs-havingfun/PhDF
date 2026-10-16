<script lang="ts">
  // Automated grading: slides down when an exam opens and asks who wrote it.
  import { onMount } from "svelte";
  import type { GradingSession } from "./grading.svelte";

  let { session, topInset }: { session: GradingSession; topInset: number } = $props();

  let input: HTMLInputElement;

  onMount(() => {
    input.focus();
    input.select();
  });

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      session.confirmIdent();
    } else if (e.key === "Escape") {
      e.preventDefault();
      session.drawer = false;
    }
  }
</script>

<div class="drawer" style="top:{topInset}px" role="dialog" aria-label="Who wrote this exam?">
  <div class="row">
    <span class="label">Exam {session.index + 1}: who is it?</span>
    <input bind:this={input} bind:value={session.ident} onkeydown={onKey} placeholder="Name or student number" spellcheck="false" />
    <button class="ok" onclick={() => session.confirmIdent()}>OK</button>
  </div>
  <span class="file">{session.exam?.rel}</span>
</div>

<style>
  .drawer {
    position: absolute;
    left: 50%;
    z-index: 8;
    width: min(460px, calc(100% - 24px));
    padding: 10px 12px 8px;
    border-radius: 0 0 14px 14px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 30px rgb(0 0 0 / 0.22);
    transform: translateX(-50%);
    animation: drop 0.22s ease-out;
  }

  @keyframes drop {
    from {
      transform: translate(-50%, -100%);
      opacity: 0;
    }
  }

  .row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .label {
    flex: none;
    font-size: 12.5px;
    font-weight: 600;
  }

  input {
    flex: 1;
    min-width: 0;
    padding: 5px 9px;
    border: none;
    border-radius: 7px;
    background: var(--hover);
    box-shadow: inset 0 0 0 1px var(--separator);
    color: var(--text);
    font: 13px var(--font);
    outline: none;
    user-select: text;
  }

  input:focus {
    box-shadow: inset 0 0 0 2px var(--accent);
  }

  .ok {
    padding: 5px 12px;
    border-radius: 7px;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 600;
  }

  .file {
    display: block;
    margin-top: 5px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: var(--tertiary);
  }
</style>
