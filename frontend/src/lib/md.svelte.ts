// A Markdown file being edited: loaded from disk, autosaved, reloaded when changed elsewhere.
import { api, type TextFile } from "./api";
import { notify } from "./notify.svelte";

const AUTOSAVE_MS = 800;

export class MdDoc {
  path = $state("");
  text = $state("");
  exists = $state(false);
  loaded = $state(false);
  saving = $state(false);
  /** The file changed elsewhere (another window or app) while this one had edits: nothing is
   *  written until the user picks Keep Mine or Load Theirs. */
  conflict = $state(false);
  /** Bumped when the text changes from outside the editor (load, reload, inserted pins). */
  revision = $state(0);
  /** Last cursor position in the editor (null until the user has clicked into it). */
  cursor: number | null = null;
  /** Ask the editor to show a position (after an insert, or a heading picked in the sidebar:
   * `heading` is its index, used by the preview). */
  reveal = $state<{ pos: number; nonce: number; heading?: number } | null>(null);

  private savedText = "";
  private mtime: number | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private writing: Promise<void> = Promise.resolve();
  private template: string;

  /** `template` is what a new file starts with (e.g. a heading); written on first change. */
  constructor(path: string, template = "") {
    this.path = path;
    this.template = template;
  }

  get name() {
    return this.path.split(/[\\/]/).pop() ?? this.path;
  }

  /** Edited and not yet written (a new file still showing its template is not "dirty"). */
  get dirty() {
    return this.text !== (this.exists ? this.savedText : this.template);
  }

  async load() {
    this.take(await (await api()).read_text(this.path));
  }

  private take(file: TextFile) {
    this.conflict = false;
    this.exists = file.exists;
    this.mtime = file.mtime;
    this.savedText = file.exists ? file.text : "";
    this.text = file.exists ? file.text : this.template;
    this.loaded = true;
    this.revision++;
  }

  /** Point at another file (e.g. after linking an existing .md). */
  async switchTo(path: string) {
    await this.flush();
    this.path = path;
    await this.load();
  }

  /** Rename the file in its folder (throws with a readable message, e.g. the name is taken). */
  async rename(name: string) {
    await this.flush();
    this.path = await (await api()).rename_file(this.path, name);
    if (this.exists) this.mtime = await (await api()).file_mtime(this.path);
  }

  /** Called by the editor on every edit. */
  edit(text: string) {
    this.text = text;
    this.scheduleSave();
  }

  /** Append a block at the end (new pins); returns the offset where it starts. */
  append(block: string): number {
    let text = this.text;
    if (text && !text.endsWith("\n\n")) text += text.endsWith("\n") ? "\n" : "\n\n";
    const at = text.length;
    this.text = text + block;
    this.revision++;
    this.flush();
    return at;
  }

  /** Insert a block as its own paragraph at the cursor (end of that line), or at the end. */
  insertBlock(block: string) {
    const text = this.text;
    let at = text.length;
    if (this.cursor !== null && this.cursor <= text.length) {
      const nl = text.indexOf("\n", this.cursor);
      at = nl < 0 ? text.length : nl;
    }
    const before = text.slice(0, at).replace(/\s*$/, "");
    const after = text.slice(at).replace(/^\s*/, "");
    const head = before ? `${before}\n\n` : "";
    const next = `${head}${block.trim()}\n\n${after}`;
    this.cursor = head.length + block.trim().length;
    this.reveal = { pos: this.cursor, nonce: Date.now() };
    this.replaceText(next.replace(/\n+$/, "\n"));
  }

  /** Replace the whole text from outside the editor (e.g. regenerated highlights). */
  replaceText(text: string) {
    this.text = text;
    this.revision++;
    this.flush();
  }

  private scheduleSave() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), AUTOSAVE_MS);
  }

  /** Write now. Writes are queued: two at once would race on the same temporary file. */
  flush(): Promise<void> {
    clearTimeout(this.timer);
    const run = this.writing.catch(() => {}).then(() => this.write());
    this.writing = run;
    return run;
  }

  private async write(force = false) {
    if (this.conflict && !force) return; // waiting for the user's choice
    if (!this.dirty && this.exists) return;
    if (!this.exists && this.text === this.template) return; // nothing worth creating a file
    const text = this.text;
    this.saving = true;
    try {
      // The time this editor last saw: a newer file on disk is not overwritten unasked.
      const expected = this.exists && !force ? this.mtime : null;
      this.mtime = await (await api()).write_text(this.path, text, expected);
      this.savedText = text;
      this.exists = true;
      this.conflict = false;
    } catch (e) {
      if (!String(e).includes("PHDF_CHANGED_ELSEWHERE")) throw e;
      this.conflict = true;
      this.askConflict();
    } finally {
      this.saving = false;
    }
  }

  /** Changed elsewhere: keep this editor's text (overwrite the file) or take the file's. */
  askConflict() {
    notify.show(
      {
        text: `“${this.name}” was changed in another window or app. Your edits here are not saved yet.`,
        error: true,
        action: { label: "Keep Mine", run: () => void this.overwrite() },
        action2: { label: "Load Theirs", run: () => void this.load() },
      },
      10 * 60_000,
    );
  }

  private overwrite(): Promise<void> {
    clearTimeout(this.timer);
    const run = this.writing.catch(() => {}).then(() => this.write(true));
    this.writing = run;
    return run;
  }

  /** Reload if the file changed on disk and there are no local edits. */
  async checkExternal() {
    if (!this.loaded || this.dirty) return;
    const mtime = await (await api()).file_mtime(this.path);
    if (mtime === null || mtime === this.mtime) return;
    const file = await (await api()).read_text(this.path);
    // Typed into meanwhile: keep those edits (autosave writes them over the file).
    if (!this.dirty) this.take(file);
  }
}
