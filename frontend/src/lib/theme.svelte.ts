// App theme (Settings → Appearance): System (follows the OS), Light or Dark. The colors live in
// app.css; `data-theme` on <html> overrides the OS setting. "Dark pages automatically" turns the
// pages dark (the moon button) whenever the app is dark.
import { api } from "./api";

export type ThemeMode = "system" | "light" | "dark";

const os = matchMedia("(prefers-color-scheme: dark)");

export const theme = $state({
  mode: "system" as ThemeMode,
  autoDarkPages: false,
  osDark: os.matches,
});

/** Whether the app is dark right now. */
export function isDark() {
  return theme.mode === "dark" || (theme.mode === "system" && theme.osDark);
}

let lastDark: boolean | null = null;
function apply() {
  const root = document.documentElement;
  if (theme.mode === "system") delete root.dataset.theme;
  else root.dataset.theme = theme.mode;
  const dark = isDark();
  if (dark === lastDark) return;
  lastDark = dark;
  api().then((py) => py.window_theme(dark)); // the native title bar (Windows)
  dispatchEvent(new CustomEvent("phdf:theme", { detail: dark })); // terminal colors, dark pages
}

os.addEventListener("change", (e) => {
  theme.osDark = e.matches;
  apply();
});

export async function loadTheme() {
  const py = await api();
  const saved = await py.get_setting<{ mode?: ThemeMode; autoDarkPages?: boolean } | null>("ui.theme", null);
  theme.mode = saved?.mode ?? "system";
  theme.autoDarkPages = saved?.autoDarkPages ?? false;
  apply();
}

function save() {
  api().then((py) => py.set_setting("ui.theme", { mode: theme.mode, autoDarkPages: theme.autoDarkPages }));
}

export function setThemeMode(mode: ThemeMode) {
  theme.mode = mode;
  save();
  apply();
}

export function setAutoDarkPages(on: boolean) {
  theme.autoDarkPages = on;
  save();
  if (on) dispatchEvent(new CustomEvent("phdf:theme", { detail: isDark() }));
}
