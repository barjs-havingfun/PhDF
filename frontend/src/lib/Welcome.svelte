<script lang="ts">
  import { kbd } from "./platform";
  import type { RecentDocument } from "./api";
  import Icon from "./Icon.svelte";
  import { ui } from "./notify.svelte";
  import LibraryBox from "./library/LibraryBox.svelte";
  import StatsBox from "./library/StatsBox.svelte";

  interface Props {
    version: string;
    recents: RecentDocument[];
    onopen: () => void;
    onnewnote: () => void;
    onopenpath: (path: string) => void;
  }

  let { version, recents, onopen, onnewnote, onopenpath }: Props = $props();

  function fileName(path: string) {
    return path.split(/[\\/]/).pop() ?? path;
  }

  function folder(path: string) {
    return path.split(/[\\/]/).slice(0, -1).join("/") || path;
  }
</script>

<section class="welcome">
  <div class="app-icon">Ph</div>
  <h1>PhDF</h1>
  <p class="hint">Version {version}</p>
  <div class="buttons">
    <button class="primary" onclick={onopen}>Open…</button>
    <button class="secondary" onclick={onnewnote}>New Note…</button>
  </div>
  <button class="tour" onclick={() => (ui.helpOpen = true)}>How to use PhDF →</button>

  {#if recents.length}
    <h2>Recents</h2>
    <ul class="card">
      {#each recents as r (r.doc_id)}
        <li>
          <button class="row" onclick={() => onopenpath(r.path)} title={r.path}>
            <span class="row-icon"><Icon name="doc" size={20} /></span>
            <span class="row-text">
              <span class="row-title">{r.title ?? fileName(r.path)}</span>
              <span class="row-sub">{folder(r.path)}</span>
            </span>
            <span class="row-meta">{r.page + 1} / {r.page_count}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
  <LibraryBox {onopenpath} />
  <StatsBox />
  <p class="hint small">{kbd("Ctrl+K find any command · Ctrl+O open · Ctrl+S save annotations")}</p>
</section>

<style>
  .welcome {
    width: min(720px, 100%);
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 6vh;
  }

  .app-icon {
    width: 72px;
    height: 72px;
    border-radius: 18px;
    display: grid;
    place-items: center;
    font: 700 30px/1 var(--font);
    letter-spacing: -1px;
    color: white;
    background: linear-gradient(160deg, #5e9bff, #3a55e8 55%, #6a3fd8);
    box-shadow:
      0 6px 16px rgb(58 85 232 / 0.35),
      inset 0 1px 0 rgb(255 255 255 / 0.35);
  }

  h1 {
    margin: 14px 0 0;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.3px;
  }

  h2 {
    align-self: flex-start;
    margin: 32px 0 8px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary);
  }

  .hint {
    margin: 2px 0 0;
    color: var(--secondary);
  }

  .hint.small {
    margin-top: 20px;
    font-size: 11px;
    color: var(--tertiary);
  }

  .buttons {
    display: flex;
    gap: 8px;
    margin-top: 18px;
  }

  .tour {
    margin-top: 10px;
    font-size: 12px;
    color: var(--accent);
  }

  .tour:hover {
    text-decoration: underline;
  }

  .secondary {
    padding: 5px 16px;
    border-radius: var(--radius-s);
    background: var(--surface);
    font-weight: 500;
    box-shadow: var(--card-shadow);
  }

  .secondary:hover {
    background: var(--hover);
  }

  .primary {
    padding: 5px 16px;
    border-radius: var(--radius-s);
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 500;
    box-shadow:
      0 1px 2px rgb(0 0 0 / 0.15),
      inset 0 0.5px 0 rgb(255 255 255 / 0.25);
  }

  .primary:hover {
    filter: brightness(1.06);
  }

  .primary:active {
    filter: brightness(0.94);
  }

  .card {
    width: 100%;
    list-style: none;
    margin: 0;
    padding: 4px;
    border-radius: var(--radius-m);
    background: var(--surface);
    box-shadow: var(--card-shadow);
  }

  .row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border-radius: var(--radius-s);
    text-align: left;
  }

  .row:hover {
    background: var(--hover);
  }

  .row:active {
    background: var(--accent);
    color: var(--accent-text);
  }

  .row:active .row-sub,
  .row:active .row-meta,
  .row:active .row-icon {
    color: inherit;
  }

  .row-icon {
    display: grid;
    color: var(--accent);
  }

  .row-text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .row-title,
  .row-sub {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .row-sub,
  .row-meta {
    font-size: 11px;
    color: var(--secondary);
  }

  .row-meta {
    font-variant-numeric: tabular-nums;
  }
</style>
