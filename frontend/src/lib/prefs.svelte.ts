// General preferences (Settings): interface size, scroll speed, unsaved tabs, start-up session,
// and which toolbar buttons are shown (right-click the toolbar).
import { api } from "./api";

export type ScrollSpeed = "slow" | "normal" | "fast";
export const SCROLL_FACTOR: Record<ScrollSpeed, number> = { slow: 0.55, normal: 1, fast: 1.8 };
export const UI_SIZES = [0.9, 1, 1.1, 1.25];

/** Toolbar buttons the user can hide; the sidebar and ⋯ buttons always stay. */
export const TOOLBAR_ITEMS = [
  ["nav", "Back and Forward"],
  ["read", "Read"],
  ["focus", "Focus"],
  ["park", "Park"],
  ["annotate", "Note, Text and Pen tools"],
  ["annotations", "Annotations panel"],
  ["note", "Note (.md)"],
  ["zoom", "Zoom"],
  ["darkpages", "Dark pages"],
  ["search", "Search"],
  ["ai", "Ask the AI (✦)"],
  ["terminal", "AI terminal"],
  ["grade", "Grading"],
  ["help", "Help (?)"],
  ["open", "Open"],
] as const;
export type ToolbarItem = (typeof TOOLBAR_ITEMS)[number][0];

export const prefs = $state({
  /** Reopen the last tabs at start ("session.restore", also read by the backend). */
  restore: true,
  uiSize: 1,
  scroll: "normal" as ScrollSpeed,
  /** Closing a tab with unsaved annotations: ask, or save without asking. */
  unsaved: "ask" as "ask" | "save",
  toolbarHidden: [] as ToolbarItem[],
});

type Saved = Partial<Pick<typeof prefs, "uiSize" | "scroll" | "unsaved" | "toolbarHidden">>;

export async function loadPrefs() {
  const py = await api();
  const saved = (await py.get_setting<Saved | null>("prefs", null)) ?? {};
  Object.assign(prefs, saved);
  prefs.restore = (await py.get_setting<boolean>("session.restore", true)) ?? true;
  if (prefs.uiSize !== 1) py.ui_zoom(prefs.uiSize);
}

function save() {
  const { uiSize, scroll, unsaved, toolbarHidden } = prefs;
  api().then((py) => py.set_setting("prefs", { uiSize, scroll, unsaved, toolbarHidden }));
}

export function setPref<K extends keyof Saved>(key: K, value: (typeof prefs)[K]) {
  prefs[key] = value;
  save();
  if (key === "uiSize") api().then((py) => py.ui_zoom(value as number));
}

export function setRestore(on: boolean) {
  prefs.restore = on;
  api().then((py) => py.set_setting("session.restore", on));
}

export const shown = (item: ToolbarItem) => !prefs.toolbarHidden.includes(item);

export function toggleToolbarItem(item: ToolbarItem) {
  setPref("toolbarHidden", shown(item) ? [...prefs.toolbarHidden, item] : prefs.toolbarHidden.filter((i) => i !== item));
}
