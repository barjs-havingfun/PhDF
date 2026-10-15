// App-wide toast: errors and short confirmations, optionally with one action button.

export interface Notice {
  text: string;
  error?: boolean;
  action?: { label: string; run: () => void };
  action2?: { label: string; run: () => void };
}

class Notifier {
  current = $state<Notice | null>(null);
  private timer: ReturnType<typeof setTimeout> | undefined;

  show(notice: Notice, ms = notice.error ? 8000 : 4500) {
    clearTimeout(this.timer);
    this.current = notice;
    this.timer = setTimeout(() => (this.current = null), ms);
  }

  error(text: string) {
    this.show({ text, error: true });
  }

  clear() {
    clearTimeout(this.timer);
    this.current = null;
  }
}

export const notify = new Notifier();

/** Settings dialog visibility, shared so any component can open it. */
export const ui = $state({ settingsOpen: false, helpOpen: false });
