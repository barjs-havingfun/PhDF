<script lang="ts">
  // One pane: its tab bar (overlaying the top, under the window toolbar) and the active tab's
  // viewer — or the welcome page. Shows drop zones while a tab is being dragged.
  import type { PdfLink, RecentDocument } from "./api";
  import { drag } from "./dnd.svelte";
  import type { Tab } from "./tab.svelte";
  import TabBar from "./TabBar.svelte";
  import Viewer from "./viewer/Viewer.svelte";
  import Welcome from "./Welcome.svelte";
  import type { Pane } from "./workspace.svelte";

  interface Props {
    pane: Pane;
    focused: boolean;
    multi: boolean; // more than one pane in the window
    toolbarHeight: number;
    invert: boolean;
    version: string;
    recents: RecentDocument[];
    onfocus: () => void;
    onopen: () => void;
    onopenpath: (path: string) => void;
    onselect: (tab: Tab) => void;
    onclose: (tab: Tab) => void;
    onnew: () => void;
    ondragstart: (e: PointerEvent, tab: Tab) => void;
    onlink: (link: PdfLink, event: MouseEvent) => void;
    onviewer: (viewer: Viewer | undefined) => void;
  }

  let {
    pane, focused, multi, toolbarHeight, invert, version, recents,
    onfocus, onopen, onopenpath, onselect, onclose, onnew, ondragstart, onlink, onviewer,
  }: Props = $props(); // prettier-ignore

  let barHeight = $state(34);
  let viewer = $state<Viewer>();

  $effect(() => onviewer(viewer));

  const zone = $derived.by(() => {
    const t = drag.target;
    if (!t || !("paneId" in t) || t.paneId !== pane.id || t.kind === "bar") return null;
    return t.kind === "split" ? t.side : "into";
  });
</script>

<section
  class="pane"
  style="flex:{pane.width} 1 0;--focus-mark:{multi ? 1 : 0}"
  data-pane-body={pane.id}
  onpointerdowncapture={onfocus}
>
  <div class="bar" style="top:{toolbarHeight}px" bind:clientHeight={barHeight}>
    <TabBar {pane} focused={focused && multi} {onselect} {onclose} {onnew} {ondragstart} />
  </div>

  {#if pane.active}
    {#key pane.active.id}
      <Viewer bind:this={viewer} tab={pane.active} topInset={toolbarHeight + barHeight} {invert} {onlink} />
    {/key}
  {:else}
    <div class="home" style="padding-top:{toolbarHeight + barHeight + 24}px">
      <Welcome {version} {recents} {onopen} {onopenpath} />
    </div>
  {/if}

  {#if zone}
    <div class="drop {zone}" style="top:{toolbarHeight + barHeight}px"></div>
  {/if}
</section>

<style>
  .pane {
    position: relative;
    min-width: 220px;
    overflow: hidden;
  }

  .bar {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 9;
    background: var(--toolbar);
    backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 0.5px solid var(--separator);
  }

  .home {
    position: absolute;
    inset: 0;
    overflow: auto;
    padding: 0 24px 32px;
    background: var(--window);
  }

  .drop {
    position: absolute;
    bottom: 8px;
    z-index: 8;
    border-radius: 10px;
    background: rgb(0 122 255 / 0.14);
    outline: 2px solid var(--accent);
    outline-offset: -2px;
    pointer-events: none;
    transition: all 0.12s ease-out;
  }

  .drop.left {
    left: 8px;
    right: 50%;
  }

  .drop.right {
    left: 50%;
    right: 8px;
  }

  .drop.into {
    left: 8px;
    right: 8px;
  }
</style>
