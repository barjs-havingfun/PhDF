<script lang="ts">
  import { kbd } from "./platform";
  import { drag } from "./dnd.svelte";
  import Icon from "./Icon.svelte";
  import type { AnyTab as Tab } from "./tab.svelte";
  import type { Pane } from "./workspace.svelte";

  interface Props {
    pane: Pane;
    focused: boolean;
    onselect: (tab: Tab) => void;
    onclose: (tab: Tab) => void;
    onnew: () => void;
    ondragstart: (e: PointerEvent, tab: Tab) => void;
  }

  let { pane, focused, onselect, onclose, onnew, ondragstart }: Props = $props();

  // Where a dragged tab would land in this bar (insertion marker), if anywhere.
  const dropIndex = $derived(
    drag.target?.kind === "bar" && drag.target.paneId === pane.id ? drag.target.index : -1,
  );
</script>

<div class="tabbar" class:focused role="tablist" data-pane-bar={pane.id}>
  {#each pane.tabs as tab, i (tab.id)}
    {#if dropIndex === i}<span class="marker"></span>{/if}
    <div
      class="tab"
      class:active={tab.id === pane.activeId}
      class:dragging={drag.tab === tab}
      data-tab-id={tab.id}
      role="tab"
      tabindex="0"
      aria-selected={tab.id === pane.activeId}
      title={tab.path}
      onpointerdown={(e) => {
        if (!(e.target as HTMLElement).closest(".close")) ondragstart(e, tab);
      }}
      onclick={() => !drag.suppressClick && onselect(tab)}
      onkeydown={(e) => e.key === "Enter" && onselect(tab)}
      onauxclick={(e) => e.button === 1 && onclose(tab)}
    >
      <button
        class="close"
        aria-label="Close tab"
        onclick={(e) => {
          e.stopPropagation();
          onclose(tab);
        }}
      >
        <Icon name="close" size={11} />
      </button>
      <span class="label">
        {#if tab.kind === "md"}<span class="md-badge">MD</span>{/if}{tab.title}
      </span>
      {#if tab.dirty}<span class="dirty" title={kbd("Unsaved annotations (Ctrl+S)")}></span>{/if}
    </div>
  {/each}
  {#if dropIndex === pane.tabs.length}<span class="marker"></span>{/if}
  <button class="new" class:active={pane.activeId === null} onclick={onnew} title={kbd("New tab (Ctrl+T)")}>
    <Icon name="plus" size={14} />
  </button>
</div>

<style>
  .tabbar {
    display: flex;
    align-items: stretch;
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
    touch-action: none;
  }

  .tab:hover {
    background: var(--hover);
  }

  .tab.active {
    background: var(--tab-active);
    color: var(--text);
    box-shadow: 0 0 0 0.5px var(--separator);
  }

  /* With several panes, the focused pane's active tab gets an accent underline. */
  .tabbar.focused .tab.active::after {
    content: "";
    position: absolute;
    left: 30%;
    right: 30%;
    bottom: 2px;
    height: 2px;
    border-radius: 1px;
    background: var(--accent);
    opacity: var(--focus-mark, 0);
  }

  .tab.dragging {
    opacity: 0.4;
  }

  .marker {
    flex: none;
    width: 2px;
    margin: 4px 0;
    border-radius: 1px;
    background: var(--accent);
  }

  .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    pointer-events: none;
  }

  .md-badge {
    margin-right: 5px;
    padding: 0 3px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 700;
    color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }

  .dirty {
    position: absolute;
    right: 9px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--secondary);
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
