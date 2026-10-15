<script lang="ts">
  // Settings sheet: Obsidian vault and OCR languages.
  import { onMount } from "svelte";
  import { api } from "./api";
  import Icon from "./Icon.svelte";
  import { notify } from "./notify.svelte";

  let { onclose }: { onclose: () => void } = $props();

  let vault = $state<string | null>(null);
  let folder = $state("PhDF");
  let installed = $state<string[]>([]);
  let common = $state<Record<string, string>>({});
  let chosen = $state<string[]>([]);
  let downloading = $state<string | null>(null);

  onMount(async () => {
    const py = await api();
    vault = await py.get_setting("obsidian.vault", null);
    folder = (await py.get_setting("obsidian.folder", "PhDF")) ?? "PhDF";
    const info = await py.ocr_info();
    installed = info.installed;
    common = info.common;
    chosen = (await py.get_setting<string[]>("ocr.languages", [])) ?? [];
  });

  async function chooseVault() {
    const py = await api();
    const path = await py.pick_folder();
    if (!path) return;
    vault = path;
    await py.set_setting("obsidian.vault", path);
  }

  async function clearVault() {
    vault = null;
    await (await api()).set_setting("obsidian.vault", null);
  }

  async function saveFolder() {
    await (await api()).set_setting("obsidian.folder", folder.trim());
  }

  async function toggle(lang: string) {
    chosen = chosen.includes(lang) ? chosen.filter((l) => l !== lang) : [...chosen, lang];
    await (await api()).set_setting("ocr.languages", chosen);
  }

  async function download(lang: string) {
    downloading = lang;
    try {
      installed = await (await api()).ocr_download(lang);
      await toggle(lang);
    } catch (e) {
      notify.error(`Download failed: ${e}`);
    } finally {
      downloading = null;
    }
  }

  const name = (code: string) => common[code] ?? code;
  const available = $derived(Object.keys(common).filter((c) => !installed.includes(c)));
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="sheet" role="dialog" aria-label="Settings">
    <header>
      <h2>Settings</h2>
      <button class="close" onclick={onclose} aria-label="Close"><Icon name="close" size={14} /></button>
    </header>

    <section>
      <h3>Obsidian</h3>
      <div class="row">
        <span class="label">Vault</span>
        <span class="value" title={vault ?? ""}>{vault ?? "Not set"}</span>
        <button class="btn" onclick={chooseVault}>Choose…</button>
        {#if vault}<button class="btn" onclick={clearVault}>Clear</button>{/if}
      </div>
      <div class="row">
        <span class="label">Folder in vault</span>
        <input bind:value={folder} onchange={saveFolder} placeholder="PhDF" spellcheck="false" />
      </div>
      <p class="hint">
        “Send to Obsidian” adds quotes to one note per book in this folder, e.g.
        <code>{folder || "PhDF"}/Attention Is All You Need.md</code>.
      </p>
    </section>

    <section>
      <h3>Text recognition (OCR)</h3>
      {#if installed.length}
        <div class="langs">
          {#each installed as lang}
            <label class="lang">
              <input type="checkbox" checked={chosen.includes(lang)} onchange={() => toggle(lang)} />
              {name(lang)} <span class="code">{lang}</span>
            </label>
          {/each}
        </div>
      {:else}
        <p class="hint">No languages yet — English is downloaded the first time you use OCR.</p>
      {/if}
      {#if available.length}
        <div class="row wrap">
          <span class="label">Download</span>
          {#each available as lang}
            <button class="btn small" onclick={() => download(lang)} disabled={downloading !== null}>
              {downloading === lang ? "Downloading…" : name(lang)}
            </button>
          {/each}
        </div>
      {/if}
      <p class="hint">Language files (~4 MB each) are stored in PhDF’s data folder.</p>
    </section>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: start center;
    padding-top: 80px;
    background: rgb(0 0 0 / 0.2);
  }

  .sheet {
    width: min(520px, 92vw);
    padding: 14px 18px 18px;
    border-radius: 14px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(30px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 20px 50px rgb(0 0 0 / 0.3);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2 {
    margin: 0;
    font-size: 15px;
  }

  h3 {
    margin: 0 0 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary);
  }

  section {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 0.5px solid var(--separator);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .row.wrap {
    flex-wrap: wrap;
  }

  .label {
    flex: none;
    width: 110px;
    color: var(--secondary);
  }

  .value {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    user-select: text;
  }

  input:not([type]) {
    flex: 1;
    height: 26px;
    padding: 0 8px;
    border: none;
    border-radius: 6px;
    background: var(--hover);
    color: var(--text);
    font: inherit;
    outline: none;
    user-select: text;
  }

  input:not([type]):focus {
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  .btn {
    flex: none;
    padding: 3px 10px;
    border-radius: 6px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  .btn:hover:not(:disabled) {
    background: var(--hover);
  }

  .btn:disabled {
    opacity: 0.5;
  }

  .btn.small {
    font-size: 12px;
  }

  .close {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 6px;
    color: var(--secondary);
  }

  .close:hover {
    background: var(--hover);
  }

  .langs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
    margin-bottom: 10px;
  }

  .lang {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .code {
    color: var(--tertiary);
    font-size: 11px;
  }

  .hint {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--secondary);
  }

  code {
    font-size: 11px;
    background: var(--hover);
    padding: 0 4px;
    border-radius: 4px;
  }
</style>
