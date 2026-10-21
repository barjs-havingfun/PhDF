// Update check: only after the user said yes (asked once, or Settings → General), PhDF asks
// GitHub for the latest release at start and shows a note when there is a newer one. Nothing
// else is sent (no network use the user didn't ask for).
import { api } from "./api";
import { notify } from "./notify.svelte";

/** PhDF's GitHub page: source, releases, bug reports. */
export const GITHUB_URL = "https://github.com/barjs-havingfun/PhDF";

/** Shown in the ⋯ menu and Settings → About while PhDF is a beta. */
export const BETA_NOTE = "PhDF is still in development and may crash. Save your work regularly (Ctrl+S).";

export const openGithub = () => api().then((py) => py.open_external(GITHUB_URL));

/** Checks once, quietly. `manual`: the user pressed "Check Now", so also say "up to date". */
export async function checkForUpdate(manual = false) {
  const py = await api();
  const r = await py.check_update();
  if (!r.ok) {
    if (manual) notify.show({ text: "Couldn't reach GitHub to check for updates." }, 3000);
    return;
  }
  if (!r.newer) {
    if (manual) notify.show({ text: `PhDF ${r.current} is the latest version.` }, 2500);
    return;
  }
  if (!manual && (await py.get_setting<string | null>("updates.skip", null)) === r.latest) return;
  notify.show(
    {
      text: `PhDF ${r.latest} is available (you have ${r.current}).`,
      action: { label: "Download", run: () => py.open_external(r.url!) },
      action2: { label: "Skip This Version", run: () => py.set_setting("updates.skip", r.latest) },
    },
    20000,
  );
}

export async function checkAtStart() {
  const py = await api();
  const allowed = await py.get_setting<boolean | null>("updates.check", null);
  if (allowed) setTimeout(() => checkForUpdate(), 8000); // after start-up work, never in its way
  if (allowed !== null) return;
  // Not asked yet: ask once, a little after the start.
  setTimeout(() => {
    notify.show(
      {
        text: "Should PhDF check for new versions when it starts? It only asks GitHub for the latest version number.",
        action: { label: "Yes, Check", run: () => py.set_setting("updates.check", true).then(() => checkForUpdate()) },
        action2: { label: "No", run: () => py.set_setting("updates.check", false) },
      },
      30000,
    );
  }, 15000);
}
