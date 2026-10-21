import { beforeEach, describe, expect, it, vi } from "vitest";

// A fake file system behind the backend calls MdDoc uses.
const disk = new Map<string, { text: string; mtime: number }>();
let reads = 0;
let onRead: (() => void) | null = null;
const py = {
  read_text: async (path: string) => {
    reads++;
    const f = disk.get(path);
    onRead?.();
    return f ? { exists: true, text: f.text, mtime: f.mtime } : { exists: false, text: "", mtime: null };
  },
  write_text: async (path: string, text: string) => {
    const mtime = (disk.get(path)?.mtime ?? 0) + 1;
    disk.set(path, { text, mtime });
    return mtime;
  },
  file_mtime: async (path: string) => disk.get(path)?.mtime ?? null,
};
vi.mock("../lib/api", () => ({ api: async () => py }));

const { MdDoc } = await import("../lib/md.svelte");

beforeEach(() => {
  disk.clear();
  reads = 0;
  onRead = null;
});

describe("MdDoc", () => {
  it("doesn't create a file for an untouched template", async () => {
    const doc = new MdDoc("/n.md", "# Title\n\n");
    await doc.load();
    expect(doc.dirty).toBe(false);
    await doc.flush();
    expect(disk.has("/n.md")).toBe(false);
  });

  it("writes edits and is clean afterwards", async () => {
    disk.set("/n.md", { text: "a", mtime: 1 });
    const doc = new MdDoc("/n.md");
    await doc.load();
    doc.edit("ab");
    expect(doc.dirty).toBe(true);
    await doc.flush();
    expect(disk.get("/n.md")!.text).toBe("ab");
    expect(doc.dirty).toBe(false);
  });

  it("reloads a file changed elsewhere", async () => {
    disk.set("/n.md", { text: "a", mtime: 1 });
    const doc = new MdDoc("/n.md");
    await doc.load();
    disk.set("/n.md", { text: "from another app", mtime: 5 });
    await doc.checkExternal();
    expect(doc.text).toBe("from another app");
  });

  it("keeps text typed while a reload was on its way", async () => {
    disk.set("/n.md", { text: "a", mtime: 1 });
    const doc = new MdDoc("/n.md");
    await doc.load();
    disk.set("/n.md", { text: "from another app", mtime: 5 });
    onRead = () => doc.edit("typed meanwhile");
    await doc.checkExternal();
    expect(doc.text).toBe("typed meanwhile");
    expect(reads).toBe(2);
  });
});

describe("changed elsewhere", () => {
  it("does not overwrite a newer file, then keeps mine when asked", async () => {
    const real = py.write_text;
    // The backend refuses when the file's time differs from the editor's.
    py.write_text = async (path: string, text: string, expected?: number | null) => {
      const f = disk.get(path);
      if (expected != null && f && f.mtime !== expected) throw new Error("PHDF_CHANGED_ELSEWHERE: the note was changed elsewhere");
      return real(path, text);
    };
    try {
      disk.set("/c.md", { text: "a", mtime: 1 });
      const doc = new MdDoc("/c.md");
      await doc.load();
      disk.set("/c.md", { text: "from the other window", mtime: 7 });
      doc.edit("mine");
      await doc.flush();
      expect(doc.conflict).toBe(true);
      expect(disk.get("/c.md")!.text).toBe("from the other window");
      doc.edit("mine, more");
      await doc.flush(); // still waiting for the choice: nothing written
      expect(disk.get("/c.md")!.text).toBe("from the other window");
      await (doc as unknown as { overwrite: () => Promise<void> }).overwrite();
      expect(disk.get("/c.md")!.text).toBe("mine, more");
      expect(doc.conflict).toBe(false);
    } finally {
      py.write_text = real;
    }
  });
});
