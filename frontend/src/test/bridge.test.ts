import { afterEach, expect, it, vi } from "vitest";

// pywebview on Linux: window.pywebview.api exists before its functions do (the 0.9.1 release
// check caught "app_info is not a function" right after start).
afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

it("waits for the API's functions, not just the object", async () => {
  const win = new EventTarget() as EventTarget & { pywebview?: { api: Record<string, unknown> } };
  win.pywebview = { api: {} };
  vi.stubGlobal("window", win);
  const { api } = await import("../lib/api");
  let got: unknown = null;
  api().then((py) => (got = py));
  await new Promise((r) => setTimeout(r, 120));
  expect(got).toBeNull(); // the object alone is not ready
  win.pywebview.api.app_info = () => ({});
  win.dispatchEvent(new Event("pywebviewready"));
  await new Promise((r) => setTimeout(r, 0));
  expect(got).toBe(win.pywebview.api);
});

it("is ready at once when the functions are already there", async () => {
  vi.stubGlobal("window", Object.assign(new EventTarget(), { pywebview: { api: { app_info: () => ({}) } } }));
  const { api } = await import("../lib/api");
  await expect(api()).resolves.toHaveProperty("app_info");
});
