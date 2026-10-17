// Markdown editor typography: font (bundled open fonts, loaded on first use) and spacing.
import { api } from "../api";

export const FONTS = {
  system: { label: "System", stack: "var(--font)", load: async () => {} },
  inter: {
    label: "Inter",
    stack: '"Inter", system-ui, sans-serif',
    load: () =>
      Promise.all([
        import("@fontsource/inter/400.css"),
        import("@fontsource/inter/400-italic.css"),
        import("@fontsource/inter/600.css"),
        import("@fontsource/inter/700.css"),
      ]),
  },
  literata: {
    label: "Literata",
    stack: '"Literata", Georgia, serif',
    load: () =>
      Promise.all([
        import("@fontsource/literata/400.css"),
        import("@fontsource/literata/400-italic.css"),
        import("@fontsource/literata/600.css"),
        import("@fontsource/literata/700.css"),
      ]),
  },
  atkinson: {
    label: "Atkinson Hyperlegible",
    stack: '"Atkinson Hyperlegible", system-ui, sans-serif',
    load: () =>
      Promise.all([
        import("@fontsource/atkinson-hyperlegible/400.css"),
        import("@fontsource/atkinson-hyperlegible/400-italic.css"),
        import("@fontsource/atkinson-hyperlegible/700.css"),
      ]),
  },
  jetbrains: {
    label: "JetBrains Mono",
    stack: '"JetBrains Mono", ui-monospace, monospace',
    load: () =>
      Promise.all([
        import("@fontsource/jetbrains-mono/400.css"),
        import("@fontsource/jetbrains-mono/400-italic.css"),
        import("@fontsource/jetbrains-mono/700.css"),
      ]),
  },
} as const;
export type FontKey = keyof typeof FONTS;

export const RANGES = {
  size: { min: 10, max: 32, step: 1, unit: "px" }, // Ctrl+wheel in a note zooms this
  lineHeight: { min: 1.2, max: 2.2, step: 0.05, unit: "" },
  letterSpacing: { min: -0.02, max: 0.12, step: 0.01, unit: "em" },
  width: { min: 480, max: 1600, step: 20, unit: "px" }, // the max means "Full": the whole pane
} as const;

const DEFAULTS = { font: "system" as FontKey, size: 14, lineHeight: 1.65, letterSpacing: 0, width: 900 };

export const typo = $state({ ...DEFAULTS });

let loaded = false;
let saveTimer: ReturnType<typeof setTimeout> | undefined;

export async function loadTypography() {
  if (loaded) return;
  loaded = true;
  const saved = await (await api()).get_setting<Partial<typeof DEFAULTS>>("md.typography", {});
  Object.assign(typo, saved ?? {});
  await FONTS[typo.font]?.load();
}

export async function setFont(font: FontKey) {
  await FONTS[font].load();
  typo.font = font;
  save();
}

export function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api().then((py) => py.set_setting("md.typography", { ...typo })), 400);
}

/** Zoom the note text (Ctrl+wheel, Ctrl+= / Ctrl+-); `0` resets to the default size. */
export function zoomText(delta: number) {
  const { min, max } = RANGES.size;
  typo.size = delta === 0 ? DEFAULTS.size : Math.min(max, Math.max(min, typo.size + delta));
  save();
}

export const DEFAULT_SIZE = DEFAULTS.size;

/** Set the note text size (px), within the zoom range. */
export function setTextSize(px: number) {
  const { min, max } = RANGES.size;
  typo.size = Math.min(max, Math.max(min, Math.round(px)));
  save();
}

/** Set the note's text width (px); the range's max means the full pane width. */
export function setTextWidth(px: number) {
  const { min, max } = RANGES.width;
  typo.width = Math.min(max, Math.max(min, Math.round(px)));
  save();
}

/** "720px", or "Full" at the top of the range. */
export const widthLabel = (v: number) => (v >= RANGES.width.max ? "Full" : `${v}px`);

export function reset() {
  Object.assign(typo, DEFAULTS);
  save();
}

// --- the whole app's font (Settings → Appearance) -----------------------------------------------

/** Fonts for the app's own text; "system" is the OS font. Notes on "System" follow this one. */
export const APP_FONTS: FontKey[] = ["system", "inter", "atkinson", "literata"];
export const ui = $state({ font: "system" as FontKey });

function applyAppFont() {
  const root = document.documentElement.style;
  if (ui.font === "system") root.removeProperty("--font");
  else root.setProperty("--font", FONTS[ui.font].stack);
}

export async function loadAppFont() {
  const saved = await (await api()).get_setting<FontKey | null>("ui.font", null);
  if (saved && saved in FONTS && saved !== "system") {
    await FONTS[saved].load();
    ui.font = saved;
    applyAppFont();
  }
}

export async function setAppFont(font: FontKey) {
  await FONTS[font].load();
  ui.font = font;
  applyAppFont();
  (await api()).set_setting("ui.font", font);
}

/** CSS custom properties for the editor and preview. */
export function typographyVars() {
  return [
    `--md-font:${FONTS[typo.font]?.stack ?? FONTS.system.stack}`,
    `--md-size:${typo.size}px`,
    `--md-line:${typo.lineHeight}`,
    `--md-letter:${typo.letterSpacing}em`,
    `--md-width:${typo.width >= RANGES.width.max ? "none" : `${typo.width}px`}`,
  ].join(";");
}
