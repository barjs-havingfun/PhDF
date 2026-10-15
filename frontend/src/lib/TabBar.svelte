<script lang="ts">
  import Icon from "./Icon.svelte";
  import type { Tab } from "./tab.svelte";

  interface Props {
    tabs: Tab[];
    activeId: number | null;
    onselect: (id: number) => void;
    onclose: (id: number) => void;
    onnew: () => void;
  }

  let { tabs, activeId, onselect, onclose, onnew }: Props = $props();
</script>

<div class="tabbar" role="tablist">
  {#each tabs as tab (tab.id)}
    <div
      class="tab"
      class:active={tab.id === activeId}
      role="tab"
      tabindex="0"
      aria-selected={tab.id === activeId}
      title={tab.doc.path}
      onclick={() => onselect(tab.id)}
      onkeydown={(e) => e.key === "Enter" && onselect(tab.id)}
      onauxclick={(e) => e.button === 1 && onclose(tab.id)}
    >
      <button
        class="close"
        aria-label="Close tab"
        onclick={(e) => {
          e.stopPropagation();
          onclose(tab.id);
        }}
      >
        <Icon name="close" size={11} />
      </button>
      <span class="label">{tab.doc.title}</span>
    </div>
  {/each}
  <button class="new" class:active={activeId === null} onclick={onnew} title="New tab (Ctrl+T)">
    <Icon name="plus" size={14} />
  </button>
</div>

<style>
  .tabbar {
    display: flex;
    gap: 1px;
    height: 30px;
    padding: 0 6px 4px;
  }

  .tab {
    position: relative;
    flex: 1 1 0;
    min-width: 0;
    max-width: 260px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 24px;
    border-radius: 7px;
    color: var(--secondary);
    font-size: 12px;
  }

  .tab:hover {
    background: var(--hover);
  }

  .tab.active {
    background: var(--tab-active);
    color: var(--text);
    box-shadow: 0 0 0 0.5px var(--separator);
  }

  .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .close {
    position: absolute;
    left: 6px;
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    border-radius: 4px;
    opacity: 0;
  }

  .tab:hover .close,
  .tab.active .close {
    opacity: 1;
  }

  .close:hover {
    background: var(--pressed);
  }

  .new {
    flex: none;
    display: grid;
    place-items: center;
    width: 28px;
    border-radius: 7px;
    color: var(--secondary);
  }

  .new:hover,
  .new.active {
    background: var(--hover);
    color: var(--text);
  }
</style>
