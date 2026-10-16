<script lang="ts">
  // Choose the default AI agent: Claude Code, Codex, any other terminal AI (its command), or none.
  import { onMount } from "svelte";
  import { api } from "../api";
  import { term } from "./terminal.svelte";

  let { current, onpick }: { current: string | null; onpick: (command: string) => void } = $props();

  const KNOWN = [
    { command: "claude", name: "Claude Code" },
    { command: "codex", name: "Codex" },
    { command: "gemini", name: "Gemini CLI" },
  ];

  let installed = $state<Record<string, boolean>>({});
  const isKnown = $derived(KNOWN.some((k) => k.command === current));
  let own = $state("");

  onMount(async () => {
    if (current && !isKnown) own = current;
    installed = await (await api()).ai_tools();
  });

  function useOwn() {
    if (own.trim()) onpick(own.trim());
  }
</script>

<div class="picker">
  <div class="known">
    {#each KNOWN as k}
      <button class="choice" class:on={current === k.command} onclick={() => onpick(k.command)}>
        <b>{k.name}</b>
        <small class:ok={installed[k.command]}>{installed[k.command] ? "✓ installed" : "not installed yet"}</small>
      </button>
    {/each}
  </div>
  <div class="own">
    <input
      bind:value={own}
      placeholder="Any other terminal AI: its command, e.g. aider"
      spellcheck="false"
      onkeydown={(e) => e.key === "Enter" && useOwn()}
    />
    <button class="btn" class:on={!!current && !isKnown && current === own.trim()} disabled={!own.trim()} onclick={useOwn}>Use</button>
  </div>
  <div class="links">
    <button class="link" onclick={() => (term.guideOpen = true)}>How to install one</button>
    <button class="link" class:on={current === ""} onclick={() => onpick("")}>No agent, just the shell</button>
  </div>
</div>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .known {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .choice {
    flex: 1 1 120px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
    text-align: left;
  }

  .choice:hover {
    background: var(--hover);
  }

  .choice.on {
    box-shadow: 0 0 0 2px var(--accent);
  }

  small {
    font-size: 11px;
    color: var(--secondary);
  }

  small.ok {
    color: #34c759;
  }

  .own {
    display: flex;
    gap: 6px;
  }

  input {
    flex: 1;
    min-width: 0;
    height: 26px;
    padding: 0 8px;
    border: none;
    border-radius: 8px;
    background: var(--hover);
    color: var(--text);
    font: inherit;
    font-size: 12px;
    outline: none;
    user-select: text;
  }

  input:focus {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .btn {
    padding: 3px 10px;
    border-radius: 8px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  .btn.on {
    box-shadow: 0 0 0 2px var(--accent);
  }

  .btn:disabled {
    opacity: 0.5;
  }

  .links {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  .link {
    font-size: 12px;
    color: var(--accent);
  }

  .link.on {
    font-weight: 600;
  }

  .link:hover {
    text-decoration: underline;
  }
</style>
