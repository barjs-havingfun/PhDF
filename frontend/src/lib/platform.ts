// Small differences between Windows / Linux and macOS in the page.

export const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
export const isWindows = /Win/.test(navigator.platform || navigator.userAgent);

/** A shortcut label as the user's keyboard shows it: "Ctrl+Shift+C" → "⇧⌘C" on a Mac. */
export function kbd(label: string): string {
  if (!isMac) return label;
  return label
    .replace(/Ctrl\+Shift\+/g, "⇧⌘")
    .replace(/Ctrl\+/g, "⌘")
    .replace(/Alt\+/g, "⌥")
    .replace(/Shift\+/g, "⇧");
}

/** Copy text. The async clipboard API is refused in some embedded browsers (WebKitGTK on Linux,
 *  older WKWebView on macOS); fall back to the old copy command there. */
export async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    // fall through
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.cssText = "position:fixed;top:-1000px;opacity:0";
  document.body.append(area);
  area.select();
  const ok = document.execCommand("copy");
  area.remove();
  if (!ok) throw new Error("The clipboard is not available");
}
