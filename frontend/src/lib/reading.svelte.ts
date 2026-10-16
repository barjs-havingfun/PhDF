// Read Mode (reading ruler, zen, full screen, page tint) and Focus (pomodoro, time left).
import { api } from "./api";
import { notify } from "./notify.svelte";
import type { Tab } from "./tab.svelte";
import type { OutlineItem } from "./api";

// --- Read Mode -----------------------------------------------------------------------------------

export const TINTS = {
  none: { label: "None", color: "transparent" },
  cream: { label: "Cream", color: "#f6e7c1" },
  blue: { label: "Blue", color: "#cfe2ff" },
  green: { label: "Green", color: "#d3f0d0" },
  gray: { label: "Gray", color: "#d6d6d6" },
} as const;
export type Tint = keyof typeof TINTS;

export const RULER_SIZES = { s: 40, m: 64, l: 100 } as const; // band height in CSS px
export type RulerSize = keyof typeof RULER_SIZES;

interface ReadSettings {
  ruler: boolean;
  rulerSize: RulerSize;
  tint: Tint;
}

export const read = $state({
  ruler: false,
  rulerSize: "m" as RulerSize,
  tint: "none" as Tint,
  zen: false, // not remembered: always start with the normal UI
  fullscreen: false,
});

export async function loadReadSettings() {
  const saved = await (await api()).get_setting<Partial<ReadSettings>>("readmode", {});
  Object.assign(read, saved ?? {});
}

export async function saveReadSettings() {
  const { ruler, rulerSize, tint } = read;
  await (await api()).set_setting("readmode", { ruler, rulerSize, tint });
}

// --- Focus: pomodoro -----------------------------------------------------------------------------

export type Phase = "idle" | "focus" | "break";

export const pomodoro = $state({
  phase: "idle" as Phase,
  running: false,
  remaining: 25 * 60, // seconds
  focusMin: 25,
  breakMin: 5,
  rounds: 0,
});

let timer: ReturnType<typeof setInterval> | undefined;

function chime() {
  try {
    const ctx = new AudioContext();
    [660, 880].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.25);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.25 + 0.4);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.25);
      osc.stop(ctx.currentTime + i * 0.25 + 0.45);
    });
  } catch {
    // no audio device
  }
}

function tick() {
  if (!pomodoro.running) return;
  pomodoro.remaining -= 1;
  if (pomodoro.remaining > 0) return;
  chime();
  if (pomodoro.phase === "focus") {
    pomodoro.rounds += 1;
    pomodoro.phase = "break";
    pomodoro.remaining = pomodoro.breakMin * 60;
    notify.show({ text: `Focus round done — take a ${pomodoro.breakMin}-minute break.` }, 10000);
  } else {
    stopPomodoro();
    notify.show({ text: "Break's over.", action: { label: "Start Focus", run: startPomodoro } }, 15000);
  }
}

export function startPomodoro() {
  if (pomodoro.phase === "idle") {
    pomodoro.phase = "focus";
    pomodoro.remaining = pomodoro.focusMin * 60;
  }
  pomodoro.running = true;
  clearInterval(timer);
  timer = setInterval(tick, 1000);
}

export function pausePomodoro() {
  pomodoro.running = false;
}

export function stopPomodoro() {
  clearInterval(timer);
  pomodoro.running = false;
  pomodoro.phase = "idle";
  pomodoro.remaining = pomodoro.focusMin * 60;
}

export function setFocusLength(min: number) {
  pomodoro.focusMin = min;
  if (pomodoro.phase === "idle") pomodoro.remaining = min * 60;
  api().then((py) => py.set_setting("pomodoro", { focusMin: min, breakMin: pomodoro.breakMin }));
}

export async function loadPomodoroSettings() {
  const saved = await (await api()).get_setting<{ focusMin: number; breakMin: number } | null>("pomodoro", null);
  if (saved) {
    pomodoro.focusMin = saved.focusMin;
    pomodoro.breakMin = saved.breakMin;
    pomodoro.remaining = saved.focusMin * 60;
  }
}

export function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// --- Focus: reading pace and time left -----------------------------------------------------------

const DEFAULT_PACE = 90; // seconds per page before we know better
export const pace = $state({ secondsPerPage: DEFAULT_PACE, samples: 0 });
let saveTimer: ReturnType<typeof setTimeout> | undefined;

export async function loadPace() {
  const saved = await (await api()).get_setting<{ secondsPerPage: number; samples: number } | null>("reading.pace", null);
  if (saved) Object.assign(pace, saved);
}

// Only time actually spent reading a page counts. A page earns "dwell" seconds while it is the
// main visible page, the window has focus, the reader was active recently and nobody is
// skimming. Skimming = the view moved more than SKIM_PAGES within SKIM_WINDOW_MS (a fling, a fast
// scroll, a jump); it wipes the current page's dwell. Wheel steps while reading and a single
// PageDown (≈ one page) stay below it.
const SKIM_WINDOW_MS = 1500;
const SKIM_PAGES = 1.2;
const IDLE_MS = 90_000;
const MIN_DWELL = 8; // s
const MAX_DWELL = 600; // s — longer means a break, not reading

const track = {
  docId: "",
  tab: -1,
  page: -1,
  dwell: 0, // seconds of real reading on `page`
  positions: [] as { at: number; pos: number }[], // recent scroll positions (page + fraction)
  skimming: false,
  lastActive: Date.now(),
};

export function noteActivity(now = Date.now()) {
  track.lastActive = now;
}

/** Scroll position of the reading view: page index + fraction within the page. */
export function noteScroll(tabId: number, pos: number, now = Date.now()) {
  if (tabId !== track.tab) track.positions = [];
  track.positions.push({ at: now, pos });
  // Keep one position from before the window as a baseline, so a single big jump counts too.
  while (track.positions.length > 2 && now - track.positions[1].at > SKIM_WINDOW_MS) track.positions.shift();
  const moved = Math.max(...track.positions.map((p) => p.pos)) - Math.min(...track.positions.map((p) => p.pos));
  if (moved > SKIM_PAGES) {
    track.skimming = true;
    track.dwell = 0;
  }
  noteActivity(now);
}

/** The main visible page changed; a finished page with a believable dwell becomes a sample. */
export function notePage(tabId: number, page: number, docId = "") {
  if (docId) track.docId = docId;
  if (tabId === track.tab && page === track.page) return;
  if (tabId === track.tab && Math.abs(page - track.page) === 1 && !track.skimming) {
    if (track.dwell >= MIN_DWELL && track.dwell <= MAX_DWELL) addSample(track.dwell);
  }
  track.tab = tabId;
  track.page = page;
  track.dwell = 0;
}

/** Called once a second. */
export function tickReading(now = Date.now(), focused = document.hasFocus()) {
  // Skimming ends once the view has been still for a moment.
  const last = track.positions[track.positions.length - 1];
  if (track.skimming && (!last || now - last.at > SKIM_WINDOW_MS)) {
    track.skimming = false;
    track.positions = last ? [last] : [];
  }
  if (track.page < 0 || !focused || track.skimming || now - track.lastActive > IDLE_MS) return;
  track.dwell += 1;
  if (track.docId) {
    unsent[track.docId] = (unsent[track.docId] ?? 0) + 1;
    if (now - lastFlush > 30_000) flushReading(now);
  }
}

// Reading time per document, sent to the backend in small batches (Library & stats).
const unsent: Record<string, number> = {};
let lastFlush = Date.now();

export function flushReading(now = Date.now()) {
  lastFlush = now;
  for (const [docId, seconds] of Object.entries(unsent)) {
    delete unsent[docId];
    if (seconds > 0) api().then((py) => py.log_reading(docId, seconds));
  }
}

function addSample(seconds: number) {
  const alpha = pace.samples < 5 ? 0.4 : 0.15;
  pace.secondsPerPage = pace.secondsPerPage * (1 - alpha) + seconds * alpha;
  pace.samples += 1;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api().then((py) => py.set_setting("reading.pace", { ...pace })), 2000);
}

/** The outline entry the page is in and the page where the next one starts. */
export function chapterAt(outline: OutlineItem[] | null, page: number, pageCount: number) {
  if (!outline?.length) return null;
  const tops = outline.filter((i) => i.page >= 0).sort((a, b) => a.page - b.page);
  let current: OutlineItem | null = null;
  let end = pageCount;
  for (const item of tops) {
    if (item.page <= page) current = item;
    else {
      end = item.page;
      break;
    }
  }
  return current ? { title: current.title, end } : null;
}

export function duration(seconds: number) {
  const min = Math.max(1, Math.round(seconds / 60));
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}
