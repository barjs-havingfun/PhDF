<script lang="ts">
  import type { OutlineItem } from "./api";
  import Icon from "./Icon.svelte";
  import Self from "./OutlineNode.svelte";

  interface Props {
    item: OutlineItem;
    current: number;
    depth?: number;
    onnavigate: (page: number) => void;
  }

  let { item, current, depth = 0, onnavigate }: Props = $props();
  let open = $state(false);
</script>

<li>
  <div class="item" class:current={item.page === current} style="padding-left:{8 + depth * 14}px">
    {#if item.children.length}
      <button class="disclosure" class:open onclick={() => (open = !open)} aria-label="Toggle">
        <Icon name="right" size={12} />
      </button>
    {:else}
      <span class="disclosure"></span>
    {/if}
    <button class="label" onclick={() => item.page >= 0 && onnavigate(item.page)} title={item.title}>
      <span class="title">{item.title}</span>
      {#if item.page >= 0}<span class="num">{item.page + 1}</span>{/if}
    </button>
  </div>
  {#if open && item.children.length}
    <ul>
      {#each item.children as child}
        <Self item={child} {current} depth={depth + 1} {onnavigate} />
      {/each}
    </ul>
  {/if}
</li>

<style>
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .item {
    display: flex;
    align-items: center;
    border-radius: var(--radius-s);
  }

  .item:hover {
    background: var(--hover);
  }

  .item.current {
    background: var(--selection);
  }

  .disclosure {
    flex: none;
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    color: var(--secondary);
    transition: transform 0.15s;
  }

  .disclosure.open {
    transform: rotate(90deg);
  }

  .label {
    flex: 1;
    min-width: 0;
    display: flex;
    gap: 6px;
    padding: 4px 8px 4px 2px;
    text-align: left;
  }

  .title {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .num {
    color: var(--secondary);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
</style>
