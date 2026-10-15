<script lang="ts" module>
  // SF Symbols–style line icons (24×24 viewBox, 1.6 stroke).
  const PATHS = {
    open: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M12 11v6M9 14h6",
    doc: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4",
    left: "M15 18l-6-6 6-6",
    right: "M9 18l6-6-6-6",
    up: "M6 15l6-6 6 6",
    down: "M6 9l6 6 6-6",
    home: "M4 11l8-7 8 7M6 9.5V20h12V9.5",
    sidebar: "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM9 5v14",
    search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
    close: "M6 6l12 12M18 6L6 18",
    expand: "M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7",
    globe:
      "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9M12 3C9.5 5.5 8.2 8.5 8.2 12s1.3 6.5 3.8 9",
    plus: "M12 5v14M5 12h14",
    minus: "M5 12h14",
    moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
  } as const;

  export type IconName = keyof typeof PATHS;
</script>

<script lang="ts">
  let { name, size = 18 }: { name: IconName; size?: number } = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.6"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  <path d={PATHS[name]} />
</svg>
