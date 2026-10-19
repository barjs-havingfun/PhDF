<script lang="ts">
  // The sheets for `ask.svelte.ts`: a PDF's password, and Save / Don't Save / Cancel.
  import logo from "../assets/logo.png";
  import { asking } from "./ask.svelte";

  let passwordValue = $state("");
  $effect(() => {
    if (asking.password) passwordValue = "";
  });
</script>

{#if asking.password}
  {@const p = asking.password}
  <div class="sheet-backdrop">
    <form class="sheet" aria-labelledby="pw-title" onsubmit={(e) => (e.preventDefault(), p.resolve(passwordValue))}>
      <img class="sheet-icon" src={logo} alt="" />
      <h2 id="pw-title">“{p.name}” is protected by a password</h2>
      <p>{p.wrong ? "That password is not right. Try again." : "Enter its password to open it. PhDF keeps it only until you quit."}</p>
      <!-- svelte-ignore a11y_autofocus -->
      <input class="pw" type="password" bind:value={passwordValue} autofocus onkeydown={(e) => e.key === "Escape" && p.resolve(null)} aria-label="Password" />
      <div class="sheet-actions">
        <span class="grow"></span>
        <button type="button" class="plain" onclick={() => p.resolve(null)}>Cancel</button>
        <button type="submit" class="default" disabled={!passwordValue}>Open</button>
      </div>
    </form>
  </div>
{/if}

{#if asking.close}
  {@const c = asking.close}
  <div class="sheet-backdrop">
    <div class="sheet" role="alertdialog" aria-labelledby="save-title">
      <img class="sheet-icon" src={logo} alt="" />
      <h2 id="save-title">Do you want to save the changes made to “{c.tab.title}”?</h2>
      <p>Your annotations will be lost if you don’t save them.</p>
      <div class="sheet-actions">
        <button class="plain" onclick={() => c.resolve("discard")}>Don’t Save</button>
        <span class="grow"></span>
        <button class="plain" onclick={() => c.resolve("cancel")}>Cancel</button>
        <button class="default" onclick={() => c.resolve("save")}>Save</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: start center;
    padding-top: 90px;
    background: rgb(0 0 0 / 0.18);
  }

  .sheet {
    width: 340px;
    padding: 20px 20px 16px;
    border-radius: 18px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(30px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 20px 50px rgb(0 0 0 / 0.3);
    text-align: center;
    animation: sheet-in 0.16s ease-out;
  }

  @keyframes sheet-in {
    from {
      opacity: 0;
      transform: translateY(-8px) scale(0.98);
    }
  }

  .sheet-icon {
    display: block;
    width: 52px;
    height: 52px;
    margin: 0 auto 10px;
  }

  .sheet h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }

  .sheet p {
    margin: 6px 0 16px;
    font-size: 12px;
    color: var(--secondary);
  }

  .pw {
    width: 100%;
    margin-top: 12px;
    padding: 6px 10px;
    border: 1px solid var(--separator);
    border-radius: 8px;
    background: var(--surface);
    color: var(--text);
    font: inherit;
  }

  .sheet-actions {
    display: flex;
    gap: 8px;
  }

  .sheet-actions .grow {
    flex: 1;
  }

  .sheet-actions button {
    padding: 4px 12px;
    border-radius: 8px;
    font-weight: 500;
  }

  .sheet-actions .plain {
    background: var(--hover);
  }

  .sheet-actions .default {
    background: var(--accent);
    color: var(--accent-text);
  }
</style>
