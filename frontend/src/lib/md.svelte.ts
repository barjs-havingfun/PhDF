// A Markdown file being edited: loaded from disk, autosaved, reloaded when changed elsewhere.
import { api } from "./api";

const AUTOSAVE_MS = 800;

export class MdDoc {
  path = $state("");
  text = $state("");
  exists = $state(false);
  loaded = $state(false);
  saving = $state(false);
  /** Bumped when the text changes from outside the editor (load, reload, inserted pins). */
  revision = $state(0);

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
    const file = await (await api()).read_text(this.path);
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

  private async write() {
    if (!this.dirty && this.exists) return;
    if (!this.exists && this.text === this.template) return; // nothing worth creating a file
    const text = this.text;
    this.saving = true;
    try {
      this.mtime = await (await api()).write_text(this.path, text);
      this.savedText = text;
      this.exists = true;
    } finally {
      this.saving = false;
    }
  }

  /** Reload if the file changed on disk and there are no local edits. */
  async checkExternal() {
    if (!this.loaded || this.dirty) return;
    const mtime = await (await api()).file_mtime(this.path);
    if (mtime !== null && mtime !== this.mtime) await this.load();
  }
}
