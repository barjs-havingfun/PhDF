// Questions the app asks in a sheet and waits for: a PDF's password, or what to do with unsaved
// marks when a tab or window closes. `AskSheets.svelte` shows them.
import type { Tab } from "./tab.svelte";

export type CloseChoice = "save" | "discard" | "cancel";

export const asking = $state<{
  password: { name: string; wrong: boolean; resolve: (pw: string | null) => void } | null;
  close: { tab: Tab; resolve: (choice: CloseChoice) => void } | null;
}>({ password: null, close: null });

/** An encrypted PDF's password (kept in memory for this session only); null = cancelled. */
export function askPassword(name: string, wrong: boolean): Promise<string | null> {
  return new Promise<string | null>((resolve) => (asking.password = { name, wrong, resolve })).finally(
    () => (asking.password = null),
  );
}

/** Save / Don't Save / Cancel for a tab with unsaved marks. */
export function askCloseChoice(tab: Tab): Promise<CloseChoice> {
  return new Promise<CloseChoice>((resolve) => (asking.close = { tab, resolve })).finally(() => (asking.close = null));
}
