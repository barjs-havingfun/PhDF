<script lang="ts">
  // Small floating card used by the selection menu and the annotation editor. Positions itself
  // above (or below) an anchor box and stays on screen.
  import type { Snippet } from "svelte";

  interface Props {
    anchor: { left: number; top: number; bottom: number; width: number };
    width?: number;
    onclose: () => void;
    children: Snippet;
  }

  let { anchor, width = 280, onclose, children }: Props = $props();
  let el = $state<HTMLElement>();

  const style = $derived.by(() => {
    const h = el?.offsetHeight ?? 60;
    const left = Math.min(Math.max(anchor.left + anchor.width / 2 - width / 2, 8), innerWidth - width - 8);
    const above = anchor.top - h - 10;
    const top = above > 60 ? above : Math.min(anchor.bottom + 10, innerHeight - h - 8);
    return `left:${left}px;top:${top}px;width:${width}px`;
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") onclose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div class="popover" bind:this={el} {style} role="dialog">
  {@render children()}
</div>

<style>
  .popover {
    position: fixed;
    z-index: 45;
    padding: 6px;
    border-radius: 11px;
    background: var(--popover);
    backdrop-filter: saturate(180%) blur(24px);
    box-shadow:
      0 0 0 0.5px var(--separator),
      0 10px 32px rgb(0 0 0 / 0.24);
    animation: pop 0.12s ease-out;
    user-select: none;
  }

  @keyframes pop {
    from {
      opacity: 0;
      transform: translateY(4px) scale(0.97);
    }
  }
</style>
