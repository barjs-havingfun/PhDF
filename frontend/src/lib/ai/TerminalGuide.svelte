<script lang="ts">
  // Terminal "How to": install and sign in to Claude Code or Codex, step by step, per OS.
  // Commands are from the official docs (code.claude.com/docs/en/setup, github.com/openai/codex).
  import { copyText } from "../platform";
  import { onMount } from "svelte";
  import { api } from "../api";
  import Icon from "../Icon.svelte";
  import { restart, typeIntoTerminal } from "./terminal.svelte";

  let { onclose }: { onclose: () => void } = $props();

  type Os = "windows" | "macos" | "linux";
  type Tool = "claude" | "codex";

  let os = $state<Os>("windows");
  let tool = $state<Tool>("claude");
  let installed = $state<Record<Tool, boolean>>({ claude: false, codex: false });
  let copied = $state<string | null>(null);

  onMount(async () => {
    const py = await api();
    os = (await py.app_info()).platform;
    installed = await py.ai_tools();
    if (installed.claude && !installed.codex) tool = "codex";
  });

  const INSTALL: Record<Tool, Record<Os, string>> = {
    claude: {
      windows: "irm https://claude.ai/install.ps1 | iex",
      macos: "curl -fsSL https://claude.ai/install.sh | bash",
      linux: "curl -fsSL https://claude.ai/install.sh | bash",
    },
    codex: {
      windows: 'powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"',
      macos: "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
      linux: "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
    },
  };

  const NAME: Record<Tool, string> = { claude: "Claude Code", codex: "Codex" };
  const MAKER: Record<Tool, string> = { claude: "Anthropic", codex: "OpenAI" };
  const SITE: Record<Tool, string> = { claude: "claude.ai", codex: "chatgpt.com" };

  const installExplain = $derived(
    os === "windows"
      ? `<code>irm</code> downloads ${MAKER[tool]}'s official install script from ${SITE[tool]}, and <code>iex</code> runs it. It installs ${NAME[tool]} for your Windows user only — no administrator rights needed, nothing else on your computer changes.`
      : `<code>curl</code> downloads ${MAKER[tool]}'s official install script from ${SITE[tool]}, and <code>| ${tool === "claude" ? "bash" : "sh"}</code> runs it. It installs ${NAME[tool]} into your home folder only — no <code>sudo</code>, nothing else on your computer changes.`,
  );

  const account = $derived(
    tool === "claude"
      ? "a browser window opens: sign in with your Claude account. Claude Code needs a <b>Pro, Max, Team or Enterprise</b> plan (or an Anthropic Console account) — the free plan doesn't include it."
      : "choose <b>Sign in with ChatGPT</b> and finish in the browser. It works with ChatGPT <b>Plus, Pro, Business, Edu or Enterprise</b> plans (an API key also works, with extra setup).",
  );

  async function type(command: string) {
    await typeIntoTerminal(command);
  }

  async function copy(command: string) {
    await copyText(command);
    copied = command;
    setTimeout(() => (copied = null), 1500);
  }
</script>

{#snippet commandBox(command: string)}
  <div class="cmd">
    <code>{command}</code>
    <button class="mini primary" onclick={() => type(command)} title="Types it into the terminal — you press Enter">
      Type in terminal
    </button>
    <button class="mini" onclick={() => copy(command)}>{copied === command ? "Copied" : "Copy"}</button>
  </div>
{/snippet}

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="sheet" role="dialog" aria-label="Set up Claude Code or Codex">
    <header>
      <span class="badge"><Icon name="terminal" size={18} /></span>
      <div>
        <h2>Set up an AI in the terminal</h2>
        <p class="sub">A few minutes, once. After that you just type <code>{tool}</code>.</p>
      </div>
      <button class="close" onclick={onclose} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>

    <div class="pickers">
      <div class="seg" role="tablist" aria-label="Your computer">
        {#each [["windows", "Windows"], ["macos", "macOS"], ["linux", "Linux"]] as [key, label]}
          <button role="tab" aria-selected={os === key} onclick={() => (os = key as Os)}>{label}</button>
        {/each}
      </div>
      <div class="seg" role="tablist" aria-label="Which AI">
        {#each ["claude", "codex"] as key}
          <button role="tab" aria-selected={tool === key} onclick={() => (tool = key as Tool)}>
            {NAME[key as Tool]}
            {#if installed[key as Tool]}<span class="ok" title="Installed on this computer">✓</span>{/if}
          </button>
        {/each}
      </div>
    </div>

    <section class="what">
      <h3>What is this terminal?</h3>
      <p>
        It is your computer's own command line ({os === "windows" ? "PowerShell" : "the shell"}), opened in the folder
        of the PDF you're reading. Whatever you type runs on <b>your</b> computer. PhDF itself sends nothing anywhere —
        {NAME[tool]} is a separate program by {MAKER[tool]} that you install once and then talk to here.
      </p>
      {#if installed[tool]}
        <p class="good">✓ {NAME[tool]} is already installed on this computer — skip to step 4.</p>
      {/if}
    </section>

    <ol>
      <li>
        <h4>Install {NAME[tool]}</h4>
        {@render commandBox(INSTALL[tool][os])}
        <!-- static, trusted text from this file -->
        <p>{@html installExplain} It shows little or no progress while downloading: wait until the prompt
          (<code>{os === "windows" ? "PS C:\\…>" : "$"}</code>) comes back.</p>
      </li>
      <li>
        <h4>Restart the terminal</h4>
        <p>A newly installed program is only found by a <i>new</i> terminal session.</p>
        <button class="mini" onclick={() => restart()}><Icon name="restart" size={12} /> Restart terminal</button>
      </li>
      <li>
        <h4>Check it worked</h4>
        {@render commandBox(`${tool} --version`)}
        <p>Prints a version number. If it says “not recognized” / “not found”, close PhDF and open it again (so it picks up the new
          program), then try once more.</p>
      </li>
      <li>
        <h4>Start it and sign in</h4>
        {@render commandBox(tool)}
        <!-- static, trusted text from this file -->
        <p>The first time, {@html account} You stay signed in afterwards.</p>
      </li>
      <li>
        <h4>Use it with your PDF</h4>
        <p>
          Select text → <b>✦ Ask AI</b> to explain, summarize or translate it; or use <b>✦ AI</b> in the toolbar for the whole
          document, a chapter or a page. You can also just type questions here. To quit {NAME[tool]}, press
          <b>Ctrl+C</b> (twice if needed).
        </p>
      </li>
    </ol>

    {#if os === "windows" && tool === "claude"}
      <p class="foot">
        Optional: <button class="link" onclick={async () => (await api()).open_external("https://git-scm.com/downloads/win")}>Git for Windows</button>
        lets Claude Code use more tools.
      </p>
    {/if}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgb(0 0 0 / 0.25);
  }

  .sheet {
    width: min(680px, 100%);
    max-height: 100%;
    overflow: auto;
    padding: 18px 22px 20px;
    border-radius: 16px;
    background: var(--popover-solid);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 24px 60px rgb(0 0 0 / 0.35);
    user-select: text;
  }

  header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .badge {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--accent);
    color: var(--accent-text);
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .sub {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--secondary);
  }

  .close {
    margin-left: auto;
    align-self: flex-start;
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    color: var(--secondary);
  }

  .close:hover {
    background: var(--hover);
  }

  .pickers {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 14px 0 10px;
  }

  .seg {
    display: flex;
    padding: 2px;
    border-radius: 8px;
    background: var(--hover);
  }

  .seg button {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--secondary);
  }

  .seg button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
  }

  .ok,
  .good {
    color: #34c759;
    font-weight: 600;
  }

  .what {
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  h3 {
    margin: 0 0 4px;
    font-size: 12px;
    color: var(--accent);
  }

  p {
    margin: 4px 0;
    font-size: 12.5px;
    line-height: 1.5;
  }

  ol {
    margin: 12px 0 0;
    padding-left: 22px;
  }

  li {
    margin-bottom: 12px;
  }

  h4 {
    margin: 0 0 4px;
    font-size: 13px;
  }

  .cmd {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 6px 6px 10px;
    border-radius: 8px;
    background: var(--window);
    box-shadow: inset 0 0 0 0.5px var(--separator);
  }

  .cmd code {
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    white-space: nowrap;
    font: 12px "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace;
  }

  code {
    font-family: "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace;
    font-size: 11.5px;
  }

  .mini {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 11.5px;
    background: var(--hover);
  }

  .mini.primary {
    background: var(--accent);
    color: var(--accent-text);
  }

  .foot {
    font-size: 11.5px;
    color: var(--secondary);
  }

  .link {
    color: var(--accent);
    font-size: inherit;
  }

  .link:hover {
    text-decoration: underline;
  }
</style>
