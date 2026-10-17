# PhDF privacy policy

Last updated: 2026-10-17

**Short version: PhDF collects nothing.** It has no account, no analytics, no telemetry and no
ads. Your documents, notes and reading history stay on your computer.

## What PhDF stores, and where

Everything is stored locally, on your own computer:

- **Your files** stay where you keep them. Annotations are written into the PDF when you save
  (Ctrl+S). Notes are Markdown files next to the PDF (`<book>.md`, `<book>.parking.md`).
- **PhDF's data folder** holds a small database (reading positions, bookmarks, reading time,
  the Library, settings), page covers, and temporary text copies made for the AI:
  - Windows: `%APPDATA%\PhDF`
  - macOS: `~/Library/Application Support/PhDF`
  - Linux: `~/.local/share/phdf`

  Settings → About shows the exact folder. Deleting it resets PhDF; your PDFs and notes are not
  in it.
- **Passwords** of protected PDFs are kept in memory only while PhDF runs, never on disk.

## When PhDF uses the internet

PhDF works offline. It goes online only when you ask it to:

- **Update check**, only if you allow it (PhDF asks once; Settings → General): at start PhDF
  asks GitHub for the number of the latest release. Nothing about you or your files is sent;
  GitHub sees the request like any web visit.
- **OCR languages**: choosing a language in Settings downloads its data file from the
  Tesseract project on GitHub.
- **Web links** you click open in a preview window or your browser, which then talks to that
  website as any browser would.
- **Obsidian**: PhDF only copies files into the vault folder you chose; nothing goes online.

## The AI terminal

PhDF has no AI of its own and no API keys. The terminal runs the AI tool you installed
yourself (for example Claude Code, Codex or Gemini CLI), with your own account. When you ask
the AI about a document, PhDF writes the needed text to a local file and the AI tool reads it.
What that tool sends to its company is covered by that company's privacy policy, not this one.

## Bug reports

Settings → About → **Copy for a Bug Report** copies versions, your data folder path and recent
error messages to the clipboard. Nothing is sent: you decide what to paste and where.

## Contact

Questions: open an issue at https://github.com/barjs-havingfun/PhDF/issues.
