// Annotation palette (macOS system colours) and labels.
import type { AnnotKind } from "../api";

export const COLORS = [
  { name: "Yellow", value: "#ffd60a" },
  { name: "Green", value: "#34c759" },
  { name: "Blue", value: "#0a84ff" },
  { name: "Pink", value: "#ff375f" },
  { name: "Purple", value: "#bf5af2" },
] as const;

export const DEFAULT_COLOR = COLORS[0].value;

export const KIND_LABEL: Record<AnnotKind, string> = {
  highlight: "Highlight",
  underline: "Underline",
  strikeout: "Strikethrough",
  note: "Note",
  freetext: "Text",
  ink: "Drawing",
  other: "Other",
};
