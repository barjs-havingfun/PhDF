// Grading mode: the exams in a folder are opened one at a time (their marked copies in
// graded/), with the folder's grades table as the note beside them. Prev / Done move through
// the exams; with "Automated" on, a drawer asks who wrote the exam and the grade is typed next
// to Done, and both go into the table.
import { api } from "../api";
import { MdDoc } from "../md.svelte";
import { notify } from "../notify.svelte";
import type { Tab } from "../tab.svelte";
import { ensureRows, getCell, setCells, toCsv } from "./table";

export interface Exam {
  num: number; // row number in the table; stays the same when files are added later
  rel: string; // path inside the folder
  name: string; // default identification (student folder or file name)
}

interface Progress {
  order: string[]; // every exam ever seen, in table order
  done: string[];
  index: number;
}

/** What the app provides: opening a path as a tab, closing a tab. */
export interface Host {
  open(path: string): Promise<Tab | null>;
  close(tab: Tab): Promise<void>;
}

export const grading = $state<{ session: GradingSession | null; automated: boolean }>({
  session: null,
  automated: true,
});

export async function loadGradingSettings() {
  grading.automated = await (await api()).get_setting("grading.automated", true);
}

export function setAutomated(on: boolean) {
  grading.automated = on;
  api().then((py) => py.set_setting("grading.automated", on));
  const s = grading.session;
  if (s) s.drawer = on && !!s.tab;
}

const progressKey = (key: string) => `grading.progress.${key}`;

export class GradingSession {
  readonly folder: string;
  readonly key: string;
  readonly title: string;
  readonly table: MdDoc;
  exams = $state<Exam[]>([]);
  index = $state(0);
  done = $state<string[]>([]);
  tab = $state<Tab | null>(null);
  /** Automated mode: the identification drawer and the grade box. */
  drawer = $state(false);
  ident = $state("");
  grade = $state("");
  busy = $state(false);

  private host: Host;
  private order: string[] = [];

  private constructor(folder: string, key: string, title: string, tablePath: string, host: Host) {
    this.folder = folder;
    this.key = key;
    this.title = title;
    this.table = new MdDoc(tablePath);
    this.host = host;
  }

  /** Scan a folder and open where grading stopped last time. Null if it has no PDFs. */
  static async start(folder: string, host: Host): Promise<GradingSession | null> {
    const py = await api();
    const found = await py.grading_scan(folder);
    if (!found.files.length) {
      notify.error(`No PDF files in ${folder}.`);
      return null;
    }
    const s = new GradingSession(found.folder, found.key, found.title, found.table, host);
    const saved = await py.get_setting<Progress | null>(progressKey(s.key), null);
    const names = new Map(found.files.map((f) => [f.rel, f.name]));
    // Keep earlier numbering; new files are added at the end.
    s.order = [...(saved?.order ?? []), ...found.files.map((f) => f.rel).filter((r) => !saved?.order.includes(r))];
    s.exams = s.order
      .map((rel, i) => ({ num: i + 1, rel, name: names.get(rel) ?? "" }))
      .filter((e) => names.has(e.rel));
    s.done = (saved?.done ?? []).filter((r) => names.has(r));

    await s.table.load();
    const text = ensureRows(s.table.text, s.title, s.order.length);
    if (text !== s.table.text) s.table.replaceText(text);
    await s.table.flush();

    grading.session = s;
    await s.show(Math.min(saved?.index ?? 0, s.exams.length - 1));
    return s;
  }

  get exam(): Exam | undefined {
    return this.exams[this.index];
  }

  isDone(exam: Exam) {
    return this.done.includes(exam.rel);
  }

  /** Open exam `i` (saving the marks on the current one first). */
  async show(i: number) {
    if (this.busy || i < 0 || i >= this.exams.length) return;
    this.busy = true;
    try {
      const previous = this.tab;
      await this.leave();
      const exam = this.exams[i];
      const path = await (await api()).grading_copy(this.folder, exam.rel);
      const tab = await this.host.open(path);
      if (!tab) return;
      this.index = i;
      this.tab = tab;
      tab.welcomeBack = false;
      tab.attachNote(this.table);
      if (previous && previous !== tab) await this.host.close(previous);
      this.ident = getCell(this.table.text, exam.num, "Name");
      tab.label = this.ident || exam.name;
      this.grade = getCell(this.table.text, exam.num, "Grade");
      this.drawer = grading.automated;
      this.saveProgress();
    } catch (e) {
      notify.error(`Could not open the exam: ${e}`);
    } finally {
      this.busy = false;
    }
  }

  /** Write what the drawer / grade box hold, and save the marks. */
  private async leave() {
    const tab = this.tab;
    if (!tab) return;
    this.commit();
    if (tab.dirty) await tab.save();
    await this.table.flush();
  }

  /** Put the identification and grade into the table (automated mode). */
  commit() {
    const exam = this.exam;
    if (!grading.automated || !exam || !this.tab) return;
    const text = setCells(this.table.text, exam.num, { Name: this.ident, Grade: this.grade });
    if (text !== this.table.text) this.table.replaceText(text);
  }

  confirmIdent() {
    this.drawer = false;
    this.commit();
    if (this.tab && this.ident.trim()) this.tab.label = this.ident.trim();
  }

  async next() {
    const exam = this.exam;
    if (!exam || this.busy) return;
    if (!this.done.includes(exam.rel)) this.done = [...this.done, exam.rel];
    if (this.index < this.exams.length - 1) return this.show(this.index + 1);
    // The last one: stay here.
    await this.leave();
    this.saveProgress();
    const left = this.exams.filter((e) => !this.isDone(e));
    notify.show(
      left.length
        ? { text: `Last exam done. ${left.length} not done yet.`, action: { label: "Go to first", run: () => this.show(this.exams.indexOf(left[0])) } }
        : { text: `All ${this.exams.length} exams graded.`, action: { label: "Export CSV", run: () => this.exportCsv() } },
      8000,
    );
  }

  prev() {
    return this.show(this.index - 1);
  }

  async exportCsv() {
    this.commit();
    await this.table.flush();
    const csv = toCsv(this.table.text);
    if (!csv) return notify.error("No grades table found in the note.");
    const path = await (await api()).save_csv(`${this.title} grades.csv`, csv);
    if (path) notify.show({ text: `Exported ${path.split(/[\\/]/).pop()}` });
  }

  /** Leave grading mode; the current exam stays open as a normal tab. */
  async stop() {
    await this.leave();
    this.saveProgress();
    this.tab?.detachNote();
    grading.session = null;
  }

  private saveProgress() {
    const progress: Progress = { order: this.order, done: this.done, index: this.index };
    api().then((py) => py.set_setting(progressKey(this.key), progress));
  }
}
