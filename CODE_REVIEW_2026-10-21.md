# PhDF v0.9.0 code review and platform readiness

Date: 2026-10-21. Reviewed the current working tree, including its existing uncommitted
v0.9.0 changes. No application source or test files were changed by this review.

## Verdict

The current code cannot be described as flawless. The backend suite failed once, and targeted
checks reproduced several additional correctness problems. Windows packaging and its self-test
passed, but that self-test does not exercise the desktop UI.

Native macOS and Linux execution was unavailable on this host. WSL is not installed, no
Docker/Podman runtime was found, and no macOS machine was available. Platform branches, the
installed pywebview 6.2.1 backend source, packaging configuration, and CI workflows were
reviewed. Those checks identify concrete compatibility concerns but do not substitute for
running the release artifacts on those operating systems. No remote CI run was triggered;
the current uncommitted tree was not uploaded or published.

## Checks actually run

| Check | Result | Scope |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | **1 failed, 105 passed, 1 skipped**, 10.08 s | Windows source backend suite |
| `npm.cmd --prefix frontend run check` | 0 errors, 0 warnings | Svelte/TypeScript static checking |
| `npm.cmd --prefix frontend test` | **19 tests passed**, 5 files | Existing frontend tests; no native GUI |
| Ruff lint | Passed | Current Python tree |
| Ruff format check | Passed, 67 files | Current Python tree |
| `npm.cmd --prefix frontend run build` | Passed | Production frontend assets |
| Source `selftest.run()` with temporary data folder | ALL OK | PDF/EPUB/CBZ, annotation save, terminal, frontend presence |
| PyInstaller build with isolated output paths | Passed, about 18 s | Current Windows executable and bundled resources |
| New Windows executable `--self-test` | Exit 0, ALL OK | Packaged engine, document formats, annotation save, terminal |
| Targeted temporary backend checks | Findings below | Exact operations, with stubs/interleavings disclosed |
| Extracted frontend-handler logic checks in Node | Findings below | Actual function bodies, not rendered UI behavior |

One OCR test was skipped for unavailable language data. This review therefore does not
establish real OCR recognition quality or complete native OCR installation behavior.

Build warnings: the editor chunk is approximately 644 kB minified, and Vite warns that the
JSON import in `vite.config.ts` needs import attributes for its future native config loader.
PyInstaller reported missing optional parser tables and unresolved OpenConsole API-set DLL
names. The packaged self-test succeeded on this Windows 11 host; the warnings alone are not
evidence that the app fails on another Windows release.

## Reproduced correctness findings

P1 means high priority because editing or source integrity is affected. P2 means a normal
feature can fail or retain incorrect state. Priorities are recommendations, not a claim that
every issue affects every user or platform.

### R1. Annotation IDs beginning with x are replaced during recreation [P1]

Source: [engine/mupdf.py](backend/phdf/engine/mupdf.py), `new_annotation_id`,
`add_annotation`, `move_annotation`, and free-text `update_annotation`.

The failing existing test was `tests/test_phase55.py::test_move_note_freetext_and_ink_keep_ids`.
It observed the old ID `xxtzz` becoming `i68b4`. Generated five-character IDs can begin with
`x`, but `add_annotation` rejects every supplied ID beginning with `x` as though it were an
external xref fallback. Ink moves and free-text edits recreate annotations through that method.

Deterministic check: force generated IDs to `xabc1`, then `abc12`; create an ink annotation
and move it. Its ID changes from `xabc1` to `abc12`, and deleting it through `xabc1` raises
`KeyError`. This establishes an actual ID-lifecycle defect, not merely a flaky assertion.
Undo operations and source-note pins that retain the old ID can fail.

Recommendation: distinguish the exact external fallback format, or carry explicit identity
provenance, rather than treating the entire `x` prefix as reserved. Preserve valid supplied
IDs during recreation. Add a deterministic regression case for x-prefixed IDs.

### R2. Discarding a protected PDF closes the document and fails to reopen it [P1]

Source: [api/core.py](backend/phdf/api/core.py), `Core.revert`.

Reproduction: create an AES-256 PDF with a user password, open it with that password, add a
note, then call `revert_document`. The call raises `PasswordRequired`. A subsequent
`text_layer` call raises `ValueError: document closed`.

Cause: revert closes the old engine document and calls `engine.open(path)` without the
password. The failed replacement leaves the old closed object in `_docs`.

Recommendation: reopen with the session credential and only replace the old object after
the new document has opened successfully. Verify password bookkeeping when saves change IDs.

### R3. Reopening a saved, already-open file leaks a document reference [P2]

Source: [api/documents.py](backend/phdf/api/documents.py), `open_document`;
[api/core.py](backend/phdf/api/core.py), aliases/acquire/release;
[App.svelte](frontend/src/App.svelte), `openPath`.

Reproduction: open PDF, add a note, save, open the same path again. The API now holds two
IDs and the same backend document has refcount 2. Closing the original tab's ID leaves one
open document and one held ID. The frontend deduplicates by path after opening, so it need
not create a second tab capable of releasing the extra reference.

Impact: memory/file handles and unsaved editing state can outlive the visible tab, until
window cleanup. Reopening can expose retained edits rather than a fresh disk document.

Recommendation: deduplicate window ownership by resolved document/file identity before
acquiring another reference, while preserving the distinction between separate PDF copies.

### R4. Extracting non-adjacent pages drops links between retained pages [P2]

Source: [services/pdftools.py](backend/phdf/services/pdftools.py), `ToolsSession._part`.

Reproduction: create three pages with a GoTo link from page 0 to page 2; extract `[0, 2]`.
Both source and target pages survive, but output page 0 has zero links.

Cause: each contiguous page run is inserted separately. Links crossing runs are not rebuilt.
The recent faster split/extract path therefore loses some navigation information.

Recommendation: retain the fast path, build a source-to-output page mapping, and rebuild
internal links whose targets survive. Test links within runs, across runs, and to omitted pages.

### R5. Concurrent note saves share one temporary filename [P1]

Source: [api/notes.py](backend/phdf/api/notes.py), `write_text`;
[md.svelte.ts](frontend/src/lib/md.svelte.ts); separate note construction in App and Tab.

The backend stages every write to `<note>.phdf-tmp`. Frontend queues are per `MdDoc`, while
standalone/integrated notes and different windows can have independent objects for one file.

Controlled reproduction: let both real writes finish staging, then allow the first real
replacement before the second. One save succeeds and the other raises `FileNotFoundError`.
The test injected synchronization barriers only; it used the production file-write method
and real filesystem operations. An unconstrained two-thread run also completed with both
calls reporting success and the last buffer winning, illustrating timing dependence.

Recommendation: serialize writes per resolved file identity and coordinate note ownership.
Unique temporary files solve the shared-temp collision but do not by themselves prevent a
stale note buffer from overwriting newer text. Surface save failures in the editor.

### R6. Discarded OCR text remains available to AI context [P2]

Source: [api/core.py](backend/phdf/api/core.py), `release`;
[api/ai.py](backend/phdf/api/ai.py), `_ai_file` / `ai_context`.

Rechecked on the current tree: OCR, create AI context, close without saving, reopen. The
reopened PDF's text does not contain the inserted word, but AI context still contains it.
The reproduction stubbed recognition and conversion to isolate revision/cache lifecycle;
it did not test actual Tesseract accuracy or the quality of Markdown extraction.

Recommendation: bind artifacts to accepted source/snapshot versions. Releasing/discarding
unsaved text must not leave a matching artifact identity for a later reopened document.

### R7. EPUB text-size changes reuse old AI page context [P2]

Source: [api/windows.py](backend/phdf/api/windows.py), `epub_text_size`;
[api/ai.py](backend/phdf/api/ai.py), cache keys.

Reproduction: the EPUB fixture grows from 3 to 16 pages at text size 24. Requesting page 1
again reuses the pre-reflow context. The converter runs only once and the cached text differs
from the current first page. Conversion was stubbed to extract actual page text from the
snapshot so the check isolates pagination/cache identity.

Recommendation: include layout version in page-scoped artifact keys; invalidate or rebuild
page-dependent text caches, outline destinations, and navigation after reflow.

### R8. The last spread's right page is excluded from the live range [P2]

Source: [viewer/Viewer.svelte](frontend/src/lib/viewer/Viewer.svelte), `pageAt`,
`liveRange`, and the `PageView.live` prop.

An isolated Node check executed the actual extracted `pageAt` body with page tops
`[0, 0, 900, 900]`. For an offset below the last spread it returns 2, so the inclusive live
upper bound is 2 and page 3 receives `live=false`. The right page exists in the mounted range
but its image/text layers depend on live state.

This is a reproduced range-calculation defect, not a native screenshot/UI reproduction.
Recommendation: expand the upper bound to the end of its row and test all layout modes.

### R9. Book-view keyboard capture consumes typing in inputs [P2]

Source: [focus/BookView.svelte](frontend/src/lib/focus/BookView.svelte), `onKey`.

An isolated check executed the actual extracted handler with Space and an INPUT target.
It called next-page and prevented the default action. The handler also handles arrows and
zoom shortcuts before checking editable targets or other dialog focus.

Recommendation: respect editable targets, terminal focus, `defaultPrevented`, and active
dialog scope in the capture handler. Existing global shortcut guards run too late to fix it.
Book view's `onlink={() => {}}` also leaves links without navigation; that is a source-inspection
finding, not a tested native interaction.

### R10. Missing-file relinking rejects an unchanged duplicate copy [P2]

Source: [api/library.py](backend/phdf/api/library.py), `library_relink`;
[api/core.py](backend/phdf/api/core.py), `copy_id`.

Reproduction: open identical A/B, close B, rename B, and select the renamed file through
the relink method. It returns `{'ok': False, 'reason': 'different'}` although bytes are unchanged.
The picker was stubbed; file creation, rename, identity checks, and result were real.

Cause: a duplicate's stored ID can be path-derived, but relink requires it to equal the
new file's raw content fingerprint. Recommendation: compare verified content identity and
update the file instance separately from its session-derived ID.

## macOS and Linux compatibility findings

### P1. Interface zoom uses the wrong native-object shape on Cocoa and GTK

Source: [services/uizoom.py](backend/phdf/services/uizoom.py), line 17.

`set_zoom` reads `window.native.webview` before selecting a platform branch. The installed
pywebview 6.2.1 Cocoa and GTK sources set `window.native` to `self.window`, an NSWindow or
Gtk.ApplicationWindow. Their WebKit view is on the backend BrowserView, not assigned as
`self.window.webview`. Cocoa also sets its view as the window content view.

The missing attribute is swallowed by `contextlib.suppress(Exception)`, so the platform
branches do not reach their zoom calls with this native-object contract. This is an API
mismatch established by reading the exact installed dependency, not by running either OS.
Fix backend-specific view lookup and add a native interaction test, with visible failure
reporting instead of silently ignoring every exception.

### P2. macOS printing can reopen PhDF instead of Preview

Source: [PrintSheet.svelte](frontend/src/lib/PrintSheet.svelte), macOS branch;
[api/documents.py](backend/phdf/api/documents.py), `open_in_default_app`.

The UI says the PDF opens in Preview, but the backend runs `open <path>`, which selects the
system default application. When PhDF is the default, that operation routes back to PhDF.
The selected page range is also not carried into this handoff, and unsaved annotations are
not included. This is a source-based behavior concern; no native print session was run.

The installed Cocoa backend already implements handling for JavaScript `window.print()`
through `BrowserView.print_webview` (`platforms/cocoa.py`, around lines 394 and 1323). The
comment claiming there is no macOS print dialog is inconsistent with that dependency source.
Test the existing native path before maintaining a platform-specific external-app fallback.

### P3. macOS bundle minimum version and architecture are not established by the workflow

[phdf.spec](phdf.spec) declares macOS 11.0 but does not select a target architecture;
[release.yml](.github/workflows/release.yml) builds once on `macos-latest`. A single runner
does not verify Intel and Apple Silicon. The frontend's installed Vite defaults include
Safari 16.4; no explicit older-webview target is configured. This does not establish support
for every macOS 11 installation merely because Info.plist allows launching it.

Inspect the actual artifact's architecture and Mach-O deployment targets, then test the
oldest declared supported OS and both supported CPU families. PyInstaller documents its
default single-architecture output and platform build compatibility constraints.
[PyInstaller feature notes](https://pyinstaller.org/en/stable/feature-notes.html),
[platform-specific usage guidance](https://pyinstaller.org/en/stable/usage.html)

### P4. macOS argv emulation needs a native launch check

[phdf.spec](phdf.spec) enables argv emulation and [macfiles.py](backend/phdf/services/macfiles.py)
also installs a Cocoa open-files handler. PyInstaller warns against argv emulation with GUI
toolkits because early event handling may interfere with the toolkit. This is a documented
risk to test, not a reproduced PhDF crash. Exercise first launch from Finder, Open With while
running, multiple files, and closing/quitting with unsaved work.
[Current PyInstaller event/argv guidance](https://pyinstaller.org/en/stable/feature-notes.html)

### P5. Current release smoke tests cannot establish a working UI

The source self-test does not open a window. On Linux its webview check imports Gtk/WebKit2;
on macOS/Windows it returns “not needed here”. The additional smoke check accepts a process
that stays alive for 20 seconds without a logged Python traceback. A blank page, failed JS
bridge, off-screen window, startup hang, broken clipboard, or dead UI can satisfy that test.

The normal CI matrix allows macOS/Linux failure through `continue-on-error`. The current
release workflow does gate the draft on all platform jobs and Linux containers, which is an
improvement. However, its macOS/Linux build steps do not run the full backend/frontend suites,
and the smoke tests do not send a frontend-ready message or complete an interaction.

Recommendation: require a loaded frontend + bridge handshake and one real open/edit/save/
reopen/close workflow in the packaged app. Run the full suites on release architectures;
retain user-facing manual checks for native dialogs, DPI, printing, clipboard and windowing.

### P6. Linux distribution coverage is useful but incomplete

The AppImage deliberately relies on the host GTK/WebKit stack. The release matrix uses
Ubuntu 24.04, Fedora, and Arch containers with Xvfb and disables WebKit's sandbox there.
That is useful ABI/startup coverage, but it does not test an ordinary non-root desktop,
Wayland behavior, actual clipboard/print dialogs, HTTPS link previews, or sandbox-enabled
WebKit. It also does not establish ARM Linux support for an x86_64 AppImage.

Test at least one ordinary user session with sandbox enabled, X11 and Wayland if supported,
and exactly the documented runtime packages. The existing typelib/environment cleanup
addresses specific prior loader problems; this inspection cannot prove every host library
combination remains compatible. [pywebview installation requirements](https://pywebview.flowrl.com/guide/installation)

### P7. Concurrent engine use remains outside the documented support model

[api/ocr_export.py](backend/phdf/api/ocr_export.py) and [api/ai.py](backend/phdf/api/ai.py)
run OCR/conversion outside `Core.lock`. These paths create and use PyMuPDF objects in the
same process while rendering may also run. The OCR helper's “Thread-safe: no shared doc”
comment is not supported by PyMuPDF's guidance, which rejects multithreaded use.

No crash was provoked during this review, so this remains an architectural risk on every
platform. Prototype process-owned extraction/OCR with immutable inputs and bounded workers;
do not deliberately induce native crashes in a working user session.
[PyMuPDF multiprocessing guidance](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html)

## Optimization findings

### Measurements on the existing local documents

Three repetitions per file in one Python process. Values below are medians on this Windows
host. Filesystem caches were not flushed; the engine store was trimmed after each iteration.
These are backend timings only, not cold app startup, webview decode, or end-to-end page turn.
Only one selected page at scale 1.0 was rendered in each repetition.

| Sample | Pages | File size | Engine open | Quick page sizes | Render page index 3 | Response bytes |
|---|---:|---:|---:|---:|---:|---:|
| Existing Film Art PDF | 655 | 207.6 MiB | 7.7 ms | 9.8 ms | 92.6 ms | 53.2 KiB |
| Existing Berserk CBZ | 233 | 501.6 MiB | 4.1 ms | 5.6 ms | 0.9 ms | 286.9 KiB |

The page-tree geometry and original-comic-image paths are worthwhile improvements. Do not
undo them to address unrelated bugs. Broader performance conclusions need more samples,
full frontend measurements, and native platform runs.

1. **Printing memory is the largest obvious resource risk.** `PrintSheet` renders/decodes
   every selected page through `Promise.all`, permitting up to 500 pages. An A4 page at
   150 DPI is roughly 8.3 MiB as four-channel decoded pixels. Five hundred are about 4 GiB
   before additional copies/caches. This is an estimate, not measured allocation or a tested
   crash. Use total-pixel budgeting, cancellation, bounded requests and a native/vector print
   route where possible. The swallowed `img.decode` error can also allow printing to proceed
   with missing page images.

2. **Book-view prefetch does not directly hand its decoded images to PageView.** The ahead
   map holds Image objects; PageView constructs another Image and later renders a separate
   `<img>`. The render server sends `no-store`. Prefetch may warm the server cache, but measure
   network requests/decode and pixel residency before claiming the held objects eliminate
   the next page's load cost. Reuse a bounded image resource/cache across both components.

3. **Avoid unbounded obsolete background work.** AI conversion jobs have no cancellation,
   registration is not atomic, and threads can outlive their source tab. Search releases
   the lock per page now, but closing or replacing a source during bulk work still needs a
   generation/token policy. Prefer one coordinated job queue over more ad hoc threads.

4. **Live math still rescans the entire note for every edit.** `md/live.ts:findMath` builds a
   full string, scans display/inline equations and repeatedly scans the block list. Use
   incremental/mapped ranges and measure a long math-heavy note before changing the parser.

5. **Thumbnail DOM is still proportional to all pages.** `content-visibility: auto` is a
   useful optimization but is not full virtualization; it does not bound node count or image
   residency by itself. Test large thumbnail grids in the actual supported WebKit versions.

6. **MuPDF cache is cleared completely every four renders.** `store_shrink(100)` controls
   memory but may re-decode reusable resources. Compare peak process memory and repeated
   scrolling latency under several bounded policies; a less aggressive policy is not
   automatically an improvement for scans.

7. **Session restore and covers still compete for shared engine time.** Restore opens tabs
   serially; cover workers issue several requests but native work is locked. Prefer active
   tab first, deferred inactive tabs, and visible-item covers over indiscriminately increasing
   parallelism, especially before the worker architecture is settled.

## Proposed implementation approaches

These are preparation for fixes, not implemented changes or verified solutions. Start with
the smallest change that preserves current behavior, then use the reproduction above as a
regression check. Avoid combining identity, cache, worker and rendering rewrites in one patch.

### Correctness fixes

| Finding | Probable approach | Verification and cautions |
|---|---|---|
| R1: annotation IDs | Identify fallback IDs by their complete format or explicit metadata. Preserve an existing annotation's stable ID when recreating its native object. Keep generated IDs compatible with existing saved notes and pins. | Force an x-prefixed ID; move ink, edit free text, undo/redo, save/reopen and resolve pins. Do not rename all historical annotations as a shortcut. |
| R2: protected revert | Open a replacement with the existing in-memory credential before closing the current document. Swap under the core lock only after successful authentication. Reset revisions and notify owners after success. | Correct/incorrect password, missing file and failed reopen must leave the original document usable. Verify successful revert removes edits and retains password protection. Never persist or log the password. |
| R3: reference ownership | Resolve aliases and existing per-window ownership before acquiring. Return an existing owned document without incrementing again, or make an open acquire an explicit lease that the frontend must release if it deduplicates. Prefer one authoritative ownership contract. | Open/save/reopen/close repeatedly and assert refcounts return to baseline. Cover two windows, two real copies, Save As and aliased IDs. Path equality alone must not merge independently editable copies. |
| R4: extracted links | Record a source-page-to-output-page mapping while inserting runs. Rebuild surviving internal GoTo links after all pages exist; retain destination coordinates and zoom. Define handling for omitted targets and repeated/reordered pages. | Check links within and across runs, excluded targets, external URLs, rotated pages and reordered selections. Avoid duplicating links already copied by the fast path. |
| R5: note saves | Coordinate writes by canonical file identity across all API instances. Serialize staging/replacement and use unique same-directory temporary files. Add a note version or expected content hash so stale editors receive a conflict instead of silently overwriting newer text. | Repeat the controlled collision, then test two windows, write failure and immediate close. Keep the editor dirty after failure. Unique temp files alone do not solve lost updates; a process-local lock does not coordinate two independent app processes. |
| R6: discarded OCR cache | Give accepted source state and unsaved text snapshots separate identities. Include the current text generation in artifact keys; retire the discarded generation on close/revert. Prevent late jobs from publishing into a newer generation. | OCR/context/discard/reopen must reflect disk text; OCR/save/reopen must retain accepted text. Include a conversion completing after close and a cache hit from a previous session. |
| R7: EPUB reflow cache | Increment a layout generation on successful reflow and include it in page-scoped cache/job keys. Invalidate page-specific artifacts and remap navigation from a stable locator where supported. | Change font size in both directions; compare current page text with context and reject late results from old layouts. Whole-book artifacts can remain reusable if they are independent of pagination. |
| R8: spread range | Compute row boundaries explicitly and expand both live-range endpoints to include every page in their row. Share row membership with mounting calculations to avoid separate interpretations. | Exercise first/last rows, odd/even totals, one page, cover mode, two-page layouts and offsets past the document end. Follow the logic regression with an actual scrolling/rendering check. |
| R9: book shortcuts | Guard capture handling with editable-target detection, composed event path, dialog/terminal scope and `defaultPrevented`. Centralize these guards with existing shortcut policy. Wire book links through the normal navigation callback. | Type spaces/arrows/zoom characters in inputs, contenteditable and editor/terminal surfaces. Confirm ordinary book shortcuts and internal/external links still work. |
| R10: duplicate relinking | Separate content fingerprint from file-instance/session ID. Compare the chosen file against the stored content fingerprint, then update its path without assuming that fingerprint equals the duplicate's ID. | Relink an unchanged renamed duplicate, reject modified content, and retain distinct identities for two copies. Legacy library rows may need a safe fingerprint backfill or an explicit revalidation path. |

Identity changes in R3/R10 should share a short design note defining content identity,
file-instance identity, session identity and ownership. Cache generations in R6/R7 should
use those definitions without turning every identifier into a content hash. This limits
another round of special cases around saves, copies, layout changes and discarded edits.

### Platform and packaging approaches

1. **Native interface zoom:** put Cocoa, GTK and Windows view lookup behind a small adapter
   tied to the supported pywebview version. Use that version's public API where available;
   otherwise isolate dependency-specific access and fail visibly when lookup breaks. Read
   native view state and apply changes on the required UI thread. Validate actual scale
   changes on each platform rather than accepting a successful API return.
2. **macOS printing:** prototype the dependency's native print path first, including page
   selection and unsaved annotations. If an external Preview fallback is required, export a
   temporary snapshot containing the selected pages and current annotations, launch Preview
   explicitly, and retain the file long enough for the receiving app. Test cancellation,
   default-app association and cleanup. Neither path is established as working by this review.
3. **macOS support contract:** choose supported CPU families and the oldest tested OS before
   changing bundle metadata. Build separate architecture artifacts or a universal bundle
   only when every native dependency supports it. Set a frontend target consistent with the
   oldest supported WebKit, then test required browser APIs separately: transpilation does
   not supply missing browser capabilities.
4. **Finder/open-file delivery:** choose one primary event-delivery mechanism after testing
   pywebview's startup behavior. If removing argv emulation, queue early open-file events
   until the bridge is ready and deduplicate initial arguments against later OS events.
   Verify cold launch and opening more files while an existing window is running.
5. **CI readiness:** add full source suites to required release jobs, then require a bounded
   frontend-ready handshake and a real bridge round trip from the packaged UI. Follow with
   a temporary-document open/edit/save/reopen check. Treat timeouts and JavaScript failures
   as failures and retain logs. A hidden or virtual-display test still needs manual native
   dialogs and desktop checks.
6. **Linux desktop coverage:** keep the container ABI checks, but add ordinary-user,
   sandbox-enabled desktop runs for supported distributions and display servers. Document
   runtime dependencies from the tested artifact. Do not treat disabling the WebKit sandbox
   as the production compatibility fix.
7. **PyMuPDF concurrency:** inventory every entry point before changing workers. As a narrow
   mitigation, evaluate serializing all engine access, including third-party conversion;
   this may block UI work and needs dependency inspection. The stronger design is a bounded
   process worker that opens its own immutable snapshot and returns serializable results.
   Do not pass live PyMuPDF objects across processes. Route rendering/conversion consistently,
   discard stale generations, propagate errors, and clean up workers on shutdown. Test frozen
   Windows/macOS startup as well as Linux before adopting the worker design.

### Optimization experiments and acceptance criteria

Record a baseline before each experiment: elapsed time, peak process memory, request count,
and user-visible latency where applicable. Compare the same documents and operations; use
several repetitions and retain memory/latency tradeoffs instead of declaring a universal win.

| Area | First experiment | Accept when |
|---|---|---|
| Printing | Prefer a native/vector document route. For raster fallback, add a decoded-pixel budget, a bounded request queue, cancellation and explicit failed-page reporting. | Peak memory is bounded on long documents and selected pages print correctly. Limiting concurrency alone is insufficient if every decoded image is retained until printing. |
| Book prefetch | Share a bounded image/resource cache keyed by document, page, render revision and scale. Evict outside the nearby-page budget; release obsolete resources on close/reflow. | Page turns improve without duplicate requests or steadily growing decoded-image memory; edits never display stale pages. Avoid holding both an unbounded prefetch cache and visible-page copies. |
| Background jobs | Deduplicate registration under a lock, attach source generations, and limit queued/running work. Add cooperative cancellation between units and reject obsolete completion results. | Repeated requests share one job, closing tabs stops unnecessary work, and shutdown leaves no workers. Hard cancellation of native work may require terminating a dedicated worker rather than a thread. |
| Markdown math | Reparse changed ranges plus enough surrounding context for delimiters; map unaffected ranges through CodeMirror changes. Fall back to a full parse for edits that change enclosing delimiter structure. | Long-note typing improves and incremental results match full parsing for multiline delimiters, pasted text and undo/redo. |
| Thumbnails | Window mounted rows with a small overscan and placeholder geometry; prioritize visible image requests and preserve stable page keys. | Node/image residency tracks the viewport rather than page count, while keyboard navigation, scroll position and accessibility remain usable. |
| MuPDF store | Benchmark the current full trim against bounded, less frequent trimming on scans and vector-heavy PDFs. | Repeated scrolling improves within an agreed peak-memory budget. Retain aggressive trimming where measurements justify it. |
| Session restore | Load the active tab first; defer inactive page geometry, covers and renders until requested. Cancel deferred work when a tab closes. | Time to first usable page improves without losing restored positions, dirty-state prompts or session ordering. |

Deliver these as small changes in the review's priority order. Each fix should include its
specific regression check and a short note describing any remaining native test requirement.
The documentation does not authorize treating the proposed solutions as completed fixes.

## Minimum native platform acceptance gate

For each supported macOS CPU/OS combination and representative Linux desktop:

- Run full backend and frontend suites against the release source.
- Build the artifact on its target platform; verify CPU architecture and minimum runtime.
- Launch as an ordinary user and require an actual frontend/bridge-ready handshake.
- Open PDF, EPUB and CBZ through the native file dialog and OS Open With route.
- Select text, annotate, save, reopen, and verify data in another reader.
- Edit a Markdown note, close immediately, reopen and verify it.
- Check interface zoom, two-page/book mode, keyboard typing, and link preview.
- Start terminal, enter a command, resize, close it, and check process cleanup.
- Exercise OCR with actual language files and invalidate search/AI context afterward.
- Test page-range printing, clipboard image/text, GTK HTTPS and native dialogs.
- Close/cancel/retry with unsaved PDF, Tools, grading and note work.
- Confirm no orphan process or unbounded memory growth after repeated open/close cycles.

For Linux, include a sandbox-enabled normal desktop rather than only the root Xvfb container.
For macOS, include Finder launch/open-files and the minimum supported WebKit capabilities.
No finite test set proves flawlessness, but this gate would support a much narrower and
defensible claim of tested platform support.

## Recommended order

1. Fix R1 annotation identity, R2 encrypted revert and R5 note-write coordination.
2. Fix R3 document ownership and the source/layout cache problems R6/R7.
3. Repair non-adjacent extraction links, live spread bounds and book keyboard scope.
4. Correct native zoom/printing and strengthen release UI readiness checks.
5. Optimize printing/prefetch/jobs using measured end-to-end memory and latency.

The current all-green packaged self-test is valuable, but this review demonstrated that it
can coexist with a failing backend regression and several reproduced behavioral defects.
