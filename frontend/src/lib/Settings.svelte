<script lang="ts">
  // Settings sheet: Obsidian vault, OCR languages and the AI (cache).
  import { onMount } from "svelte";
  import { api } from "./api";
  import Icon from "./Icon.svelte";
  import { notify, ui as appUi } from "./notify.svelte";
  import { copyText } from "./platform";
  import type { AboutInfo } from "./api";
  import licenses from "../assets/licenses.json";
  import { setAutoDarkPages, setThemeMode, theme, type ThemeMode } from "./theme.svelte";
  import { prefs, setPref, setRestore, UI_SIZES, type ScrollSpeed } from "./prefs.svelte";
  import { chime, pomodoro, setFocusLength, setPomodoro } from "./reading.svelte";
  import { checkForUpdate } from "./updates";
  import { isMac } from "./platform";

  let checkUpdates = $state(false);
  api()
    .then((py) => py.get_setting<boolean | null>("updates.check", null))
    .then((v) => (checkUpdates = !!v));
  async function toggleUpdates() {
    checkUpdates = !checkUpdates;
    await (await api()).set_setting("updates.check", checkUpdates);
  }

  async function makeDefault() {
    const { result } = await (await api()).make_default_app();
    const text = {
      settings: "In Windows Settings, choose PhDF for .pdf (and .epub if you like).",
      "settings-unregistered": "Windows Settings opened: search for .pdf and choose PhDF. (Installed with the PhDF installer, PhDF appears there by name.)",
      done: "PhDF is now the default app for PDF files.",
      howto: isMac
        ? "In Finder: select a PDF → File → Get Info → Open with: PhDF → Change All…"
        : "Right-click a PDF in your file manager → Open With → PhDF, and set it as default.",
    }[result];
    notify.show({ text }, 9000);
  }
  import AgentPicker from "./ai/AgentPicker.svelte";
  import { APP_FONTS, FONTS, setAppFont, ui } from "./md/typography.svelte";
  import { loadAgent, setAgent, setFont, term, TERM_FONTS, TERM_SIZES } from "./ai/terminal.svelte";

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
    cache = await py.ai_cache_info();
    await loadAgent();
    agentReady = true;
  });

  let agentReady = $state(false);

  async function toggleMotion() {
    appUi.reduceMotion = !appUi.reduceMotion;
    await (await api()).set_setting("ui.reduceMotion", appUi.reduceMotion);
  }

  // About: versions and storage, copied as one text for bug reports.
  let about = $state<AboutInfo | null>(null);
  api()
    .then((py) => py.about())
    .then((a) => (about = a));
  function aboutText(a: AboutInfo) {
    const lines = [
      `PhDF ${a.version}${a.frozen ? " (app)" : " (source)"}`,
      `OS: ${a.os}`,
      `Python ${a.python}, PyMuPDF ${a.pymupdf}, pywebview ${a.pywebview}${a.gui ? ` (${a.gui})` : ""}`,
      `Web view: ${navigator.userAgent}`,
      `Data folder: ${a.dataDir}`,
      `Database ${mb(a.dbBytes)}, AI cache ${mb(a.aiCacheBytes)}, covers ${mb(a.coverBytes)}`,
      `OCR languages: ${a.ocrLanguages.join(", ") || "none"}`,
      "",
      "Recent errors:",
      ...(notify.recent.length ? notify.recent.map((e) => `${e.time}  ${e.text}`) : ["none"]),
    ];
    return lines.join(String.fromCharCode(10));
  }
  const SOURCE = "https://github.com/barjs-havingfun/PhDF";
  let showLicenses = $state(false);
  const openLink = (url: string) => api().then((py) => py.open_external(url));

  async function copyAbout() {
    if (!about) return;
    await copyText(aboutText(about));
    notify.show({ text: "Copied. Paste it into a bug report." }, 2000);
  }

  let perMonitorDpi = $state(true);
  api()
    .then((py) => py.get_setting<boolean>("window.perMonitorDpi", true))
    .then((v) => (perMonitorDpi = v ?? true));

  async function togglePerMonitorDpi() {
    perMonitorDpi = !perMonitorDpi;
    await (await api()).set_setting("window.perMonitorDpi", perMonitorDpi);
    notify.show({ text: "Restart PhDF for this to take effect." }, 3000);
  }

  async function pickAgent(command: string) {
    await setAgent(command);
    notify.show({ text: command ? "Default AI agent saved. New terminals start it." : "New terminals start a plain shell." }, 2200);
  }

  let cache = $state<{ files: number; bytes: number } | null>(null);

  async function clearCache() {
    cache = await (await api()).ai_cache_clear();
    notify.show({ text: "AI cache cleared." }, 1800);
  }

  const mb = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

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
      <h3>Appearance</h3>
      <div class="row">
        <span class="label">Theme</span>
        <div class="fonts">
          {#each [["system", "System"], ["light", "Light"], ["dark", "Dark"]] as [mode, label] (mode)}
            <button class="font" class:on={theme.mode === mode} onclick={() => setThemeMode(mode as ThemeMode)}>{label}</button>
          {/each}
        </div>
      </div>
      <label class="check-row">
        <input type="checkbox" checked={theme.autoDarkPages} onchange={(e) => setAutoDarkPages(e.currentTarget.checked)} />
        <span>
          Dark pages automatically when the theme is dark
          <small>Pages turn dark with the app (like the moon button) and light again with it.</small>
        </span>
      </label>
      <div class="row">
        <span class="label">Interface size</span>
        <div class="fonts">
          {#each UI_SIZES as size (size)}
            <button class="font" class:on={prefs.uiSize === size} onclick={() => setPref("uiSize", size)}>{Math.round(size * 100)} %</button>
          {/each}
        </div>
      </div>
      <div class="row">
        <span class="label">App font</span>
        <div class="fonts">
          {#each APP_FONTS as key}
            <button class="font" class:on={ui.font === key} style="font-family:{FONTS[key].stack}" onclick={() => setAppFont(key)}>
              {FONTS[key].label}
            </button>
          {/each}
        </div>
      </div>
      <p class="hint">The font of PhDF's buttons, menus and notes set to “System”. Notes have their own font under <b>Aa</b>.</p>
      <label class="check-row">
        <input type="checkbox" checked={perMonitorDpi} onchange={togglePerMonitorDpi} />
        <span>
          Sharp on every monitor
          <small>For monitors with different scaling (e.g. 150 % and 100 %). Takes effect after restarting PhDF.</small>
        </span>
      </label>
      <label class="check-row">
        <input type="checkbox" checked={appUi.reduceMotion} onchange={toggleMotion} />
        <span>
          Fewer animations
          <small>Cards, page turns and menus appear without sliding or fading.</small>
        </span>
      </label>
    </section>

    <section>
      <h3>General</h3>
      <label class="check-row">
        <input type="checkbox" checked={prefs.restore} onchange={(e) => setRestore(e.currentTarget.checked)} />
        <span>
          Reopen my last tabs when PhDF starts
          <small>Off: PhDF starts with an empty window (your books stay in the Library).</small>
        </span>
      </label>
      <label class="check-row">
        <input type="checkbox" checked={checkUpdates} onchange={toggleUpdates} />
        <span>
          Check for updates when PhDF starts
          <small>Asks GitHub for the latest version number; nothing else is sent. Off until you turn it on.</small>
        </span>
      </label>
      <div class="row">
        <button class="btn" onclick={makeDefault}>Make PhDF the Default PDF App…</button>
        <button class="btn" onclick={() => checkForUpdate(true)}>Check for Updates Now</button>
      </div>
      <div class="row">
        <span class="label">Scroll speed</span>
        <div class="fonts">
          {#each [["slow", "Slow"], ["normal", "Normal"], ["fast", "Fast"]] as [speed, label] (speed)}
            <button class="font" class:on={prefs.scroll === speed} onclick={() => setPref("scroll", speed as ScrollSpeed)}>{label}</button>
          {/each}
        </div>
      </div>
      <div class="row">
        <span class="label">Closing with unsaved marks</span>
        <div class="fonts">
          <button class="font" class:on={prefs.unsaved === "ask"} onclick={() => setPref("unsaved", "ask")}>Ask me</button>
          <button class="font" class:on={prefs.unsaved === "save"} onclick={() => setPref("unsaved", "save")}>Save automatically</button>
        </div>
      </div>
    </section>

    <section>
      <h3>Focus timer</h3>
      <div class="row">
        <span class="label">Focus</span>
        <div class="fonts">
          {#each [15, 25, 45, 50] as min (min)}
            <button class="font" class:on={pomodoro.focusMin === min} onclick={() => setFocusLength(min)}>{min} min</button>
          {/each}
        </div>
      </div>
      <div class="row">
        <span class="label">Break</span>
        <div class="fonts">
          {#each [5, 10, 15] as min (min)}
            <button class="font" class:on={pomodoro.breakMin === min} onclick={() => setPomodoro({ breakMin: min })}>{min} min</button>
          {/each}
        </div>
      </div>
      <label class="check-row">
        <input type="checkbox" checked={pomodoro.chime} onchange={(e) => setPomodoro({ chime: e.currentTarget.checked })} />
        <span>Chime when a round or a break ends</span>
      </label>
      {#if pomodoro.chime}
        <div class="row">
          <span class="label">Volume</span>
          <input class="volume" type="range" min="0.05" max="1" step="0.05" value={pomodoro.volume} oninput={(e) => setPomodoro({ volume: Number(e.currentTarget.value) })} aria-label="Chime volume" />
          <button class="btn small" onclick={() => chime(true)}>Test</button>
        </div>
      {/if}
    </section>

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
        <p class="hint">No languages yet. English is downloaded the first time you use OCR.</p>
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

    <section>
      <h3>AI</h3>
      <p class="hint top">Default agent: started in new terminals and when you <i>Ask AI</i> with none running.</p>
      {#if agentReady}
        <AgentPicker current={term.agent} onpick={pickAgent} />
        <p class="hint">This choice applies the next time a terminal opens; an agent that is already running keeps running.</p>
      {/if}
      <div class="row term-font">
        <span class="label">Terminal font</span>
        <select value={term.font.name} onchange={(e) => setFont({ name: e.currentTarget.value })}>
          {#each TERM_FONTS as f}<option value={f.name}>{f.name}</option>{/each}
        </select>
        <input
          type="number"
          min={TERM_SIZES.min}
          max={TERM_SIZES.max}
          value={term.font.size}
          onchange={(e) => setFont({ size: Number(e.currentTarget.value) })}
          aria-label="Terminal font size"
        />
        <span class="unit">px</span>
      </div>
      <div class="row cache">
        <span class="label">Cache</span>
        <span class="value">{cache ? `${cache.files} file${cache.files === 1 ? "" : "s"}, ${mb(cache.bytes)}` : "…"}</span>
        <button class="btn" onclick={clearCache} disabled={!cache?.files}>Clear AI cache</button>
      </div>
      <p class="hint">
        Markdown copies of documents the AI reads (✦ menu). PhDF keeps them small by itself: only the latest version
        of each document, nothing unused for 30 days, at most 500 MB.
      </p>
    </section>

    <section>
      <h3>About</h3>
      {#if about}
        <pre class="about">{aboutText(about)}</pre>
        <div class="row">
          <button class="btn" onclick={copyAbout}>Copy for a Bug Report</button>
        </div>
        <p class="hint">Nothing is sent anywhere. Check the text before sharing it: it shows your data folder.</p>
        <p class="free">
          PhDF is free software under the <b>GNU Affero General Public License v3.0</b> (or later): you may use, share and change it. If you share a
          changed version, share its source code too.
        </p>
        <div class="row">
          <button class="btn" onclick={() => openLink(SOURCE)}>Source Code</button>
          <button class="btn" onclick={() => openLink(`${SOURCE}/blob/main/LICENSE`)}>License</button>
          <button class="btn" onclick={() => openLink(`${SOURCE}/blob/main/PRIVACY.md`)}>Privacy</button>
          <button class="btn" onclick={() => (showLicenses = !showLicenses)} aria-expanded={showLicenses}>
            Open-Source Licenses ({licenses.length})
          </button>
        </div>
        {#if showLicenses}
          <ul class="licenses">
            {#each licenses as l (l.name)}
              <li>
                {#if l.url}<button class="link" onclick={() => openLink(l.url)}>{l.name}</button>{:else}<span>{l.name}</span>{/if}
                <span class="ver">{l.version}</span>
                <span class="lic">{l.license}</span>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
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
    max-height: calc(100vh - 120px);
    overflow-y: auto;
    padding: 14px 18px 18px;
    border-radius: 18px;
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
    border-radius: 8px;
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
    border-radius: 8px;
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
    border-radius: 8px;
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

  .volume {
    flex: 1;
    max-width: 200px;
  }

  .free {
    margin: 12px 0 8px;
    line-height: 1.5;
  }

  .licenses {
    max-height: 220px;
    overflow: auto;
    margin: 8px 0 0;
    padding: 6px 10px;
    list-style: none;
    border-radius: 8px;
    background: var(--hover);
    font-size: 12px;
  }

  .licenses li {
    display: flex;
    gap: 8px;
    padding: 2px 0;
  }

  .licenses .link {
    color: var(--accent);
    text-align: left;
  }

  .licenses .ver {
    color: var(--tertiary);
  }

  .licenses .lic {
    margin-left: auto;
    color: var(--secondary);
    text-align: right;
  }

  .about {
    margin: 0 0 8px;
    padding: 10px 12px;
    max-height: 180px;
    overflow: auto;
    border-radius: 8px;
    background: var(--hover);
    font: 11.5px/1.5 ui-monospace, Consolas, monospace;
    white-space: pre-wrap;
    word-break: break-all;
    user-select: text;
  }

  .hint {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--secondary);
  }

  .check-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 10px;
  }

  .check-row small {
    display: block;
    font-size: 11px;
    color: var(--secondary);
  }

  .fonts {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .font {
    padding: 4px 10px;
    border-radius: 9px;
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  .font.on {
    box-shadow: 0 0 0 2px var(--accent);
  }

  .hint.top {
    margin: 0 0 8px;
  }

  .row.cache,
  .row.term-font {
    margin-top: 12px;
  }

  select,
  input[type="number"] {
    height: 26px;
    padding: 0 6px;
    border: none;
    border-radius: 8px;
    background: var(--hover);
    color: var(--text);
    font: inherit;
  }

  input[type="number"] {
    width: 60px;
  }

  .unit {
    color: var(--secondary);
    font-size: 12px;
  }

  code {
    font-size: 11px;
    background: var(--hover);
    padding: 0 4px;
    border-radius: 5px;
  }
</style>
