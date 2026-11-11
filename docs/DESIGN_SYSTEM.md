# Design system: "As Found / As Left"

Every project page is a self-issued verification record: an instrument (the tool), a reference standard (what it was checked against), a reading as found and as left, limits, and traceability to CI runs. The calibration vocabulary appears only in labels and data objects; prose is plain English. Records always say "Self-issued verification record, not accredited". Never use accreditation or standards-body language for them.

Source of the decision: the design brief in the vault (`18-Portfolio-Design/DESIGN_BRIEF.md`). This file documents what is implemented.

## Files

| Path | Role |
|---|---|
| `assets/css/site.css` | All styles, one file (about 26 KB raw, 6.9 KB gzip). Sections: fonts, tokens, base, layout, components, pages, motion, print and forced colors |
| `assets/js/site.js` | Global script, about 2 KB: theme toggle and copy buttons. Everything works without it |
| `assets/js/bench-NAME.js` | Optional per-page bench module (see below) |
| `assets/fonts/` | Unmodified official woff2 files from Fontsource (Source Serif 4 variable latin; IBM Plex Mono 400 and 600 latin) and their OFL texts. Do not subset or rename them |
| `assets/og.png`, `scripts/og/og.html` | Open Graph image (1200x630, 14 KB) and its HTML source. Regenerate with headless Chrome `--window-size=1200,630 --screenshot` |
| `scripts/build.py` | Page registry, layout, redirects, sitemap, robots |
| `scripts/pages.py` | Home, projects index and project-page bodies |
| `scripts/components.py` | Strips, stamps, chips, diagrams, table labels |
| `content/data/projects.json` | Per-project data: record head, reading, strip runs, ledger texts, links, traceability, "what failed first" |
| `content/data/runs.json` | State and date of every GitHub Actions run shown as a chip, captured with `gh api`. Refresh when a chip's run changes |
| `assets/js/bench-sinkline.js`, `assets/data/bench-sinkline.json`, `assets/data/sinkline-bench/` | The sinkline "Sanitizer switch": the module (2.1 KB gzip), the recorded data (2.0 KB gzip) and the nine small Flask files with the unedited `sinkline scan` output beside each (`.py` and `.txt`) |
| `scripts/capture_sinkline_bench.py`, `scripts/test_bench_sinkline.mjs`, `scripts/bench_static.py` | Capture (`--check` re-runs the real CLI and compares), Node parity test, and the generator of the no-JS record for that bench |
| `content/<project>.html` | Prose for one project, split by `<!--@name-->` markers (below) |

Run `python scripts/build.py` after any change; the generated HTML is committed.

## Tokens

Defined on `:root` in `site.css`. Light values are plain declarations (fallback); `light-dark()` is used where supported with `color-scheme: light dark`; an explicit dark block covers browsers without `light-dark()`. `data-theme="light|dark"` on `<html>` (set by the toggle, persisted in `localStorage` inside try/catch, applied before paint by a tiny inline script) overrides the OS setting.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` / `--sheet` | #F3EFE6 / #FBF9F4 | #14161A / #1B1E23 | page ground / raised surface |
| `--ink`, `--ink-2`, `--ink-3` | #1B1D21, #4A4D54, #656A72 | #ECE8DD, #B4B6B0, #9A9D97 | text (ink-3 for labels 13 px and up only) |
| `--stamp` | #A82E1B | #FF907A | as found, failed |
| `--ok` | #1D5C47 | #74D2AB | confirmed |
| `--warn` | #7A5200 | #E7B65C | limits |
| `--link`, `--focus` | #1F3A93 | #A6B9FF | links, focus ring |
| `--rule` / `--edge` | #CFC8B8 / #7D7868 | #383B41 / #6C7078 | decorative hairline / meaningful border (3:1) |
| `--hatch` | #E6DFCF | #24272D | hatch ground |
| `--*-tint` | `color-mix` of the colour into `--paper` | | fills for failed rows and limits |

Type: `--serif` (Source Serif 4, text and headings), `--mono` (IBM Plex Mono, every identifier, number and label). Scale `--step--1` to `--step-4` and `--reading` (the giant numeral). Fallback faces ("Serif Fallback", "Data Fallback", ...) use `size-adjust` and ascent/descent overrides computed from font metrics, so the swap from system fonts moves nothing. Only the serif roman file is preloaded. Spacing `--s-1` to `--s-9`, `--gutter`, `--page` (76 rem).

## Components

All are plain HTML with classes; none needs JS.

- **Header**: wordmark, `Primary` nav (Work, Experience, About, Resume; `aria-current` plus a 2 px underline), theme toggle (`#theme`, `aria-pressed`, hidden until JS runs). Project pages add `Sheet n of 6` under it.
- **Record head** (`.record-head > dl > div > dt + dd`): Instrument, Reference standard, Measured on, Issued by, Reproduce (copyable `pre`).
- **The reading** (`.reading`, optional `.sm`): mono 600 numeral with `.den`. Give it `role="img"` and an `aria-label` and hide the glyph spans.
- **Verdict stamp** (`.stamp` + `.fail | .pass | .limit | .pend`): always contains text. Built with `components.stamp()`, or `{{stamp:fail:As found: fail}}` in content.
- **Evidence chip** (`.chip[data-s=pass|fail|pend]`): state shape (filled square, hatched, dotted), `run ID`, state word and date. `{{run:ID}}` in content; the state comes from `content/data/runs.json`, never from the network at runtime.
- **Ruler strip** (`.strips > .srow > .label + .strip + .val`; `.strips.mini` for the 24-tick form): ticks are `<i data-s="hit|miss|neg|pend|fp">`. Filled = observed, hatched = expected but missed, outline = not expected, dotted = pending, half-filled = reported where nothing was expected. Every tenth tick is taller and numbered. `.strip` has `role="img"` and an `aria-label` such as "As found, 36 events: 34 not expected and not matched, 2 expected but not matched"; the ticks carry no information for assistive technology, and state never depends on colour (forced-colors keeps shapes). A strip set may carry `"per": N` (one drawn tick stands for about N items; the tick numbers are then omitted, the legend says so, and the `aria-label` keeps the true counts). Strip data lives in `projects.json` as run-lengths (`["neg", 13], ["miss", 1], ...`); `components.normalize()` reduces to at most 24 ticks for small multiples and keeps every non-empty run visible. The legend is `{{key:NAME}}`. Entrance animation (opacity and transform, scroll-driven, grouped by tens) is CSS only and absent under `prefers-reduced-motion`.
- **Figure plate** (`.plate`, `.plate-label`, `figcaption`): label `Plate {{n}}` is numbered automatically in document order. The caption states the claim the figure supports.
- **Diagram plate**: `{{diagram:NAME}}` renders hand-written SVG (mono labels, square corners, orthogonal connectors, open arrowheads, lettered steps, hatched bar for the failing step) with `<title>`, `<desc>`, a caption and a "Describe this diagram" `details` listing the steps. Add diagrams in `components.DIAGRAMS`.
- **Margin note** (`<aside class="note">` after the paragraph it annotates, with `<sup class="nref" aria-hidden="true"></sup>` in the paragraph): numbered by CSS counters. In the margin column from 64 rem, a boxed inline note below. The build emits it as `<div class="note" role="note">`.
- **Result table** (`table.tbl`): header cells `th scope="col"`, row headers `th scope="row"`. The build adds `data-label` to each `td`, and below 48 rem (below 64 rem with `.wt`) the table collapses to cards. Numbers use `.num` (tabular, right-aligned). `b.best` marks the best value with a filled square. `tr.row-fail` tints a failed row.
- **Code or output block**: `<pre data-copy data-label="..."><code>`; the label bar is CSS, the copy button is added by `site.js`.
- **Limits box** (`.limits`): placed right after the method, never in a footer.
- **Sheets nav** (`.sheets`): previous and next sheet.

## Project page template

`pages.project_page()` assembles, in order: title block, record head, reading band (numeral, caption, stamp, chip, legend, strip pair with the view-transition name), bench slot, `#as-found`, `#as-left`, `#method`, `#limits`, `#trace`, sheets nav. Prose comes from `content/<project>.html`, split into named chunks:

`<!--@dek-->` one-sentence description, `<!--@bench-->` and `<!--@bench-cap-->` static state and caption for Plate 1, `<!--@as-found-->`, `<!--@as-left-->`, `<!--@method-->`, `<!--@limits-->` (a `ul`), optional `<!--@trace-->` (extra tables after the generated traceability list).

Section labels follow `labels` in `projects.json`: "As found" and "As left" only where something was actually fixed; otherwise "Reference" and "Reading". Placeholders usable in any content file: `{{bench:sinkline}}` and `{{bench:sinkline-cap}}` (the generated static record and caption of the sinkline bench), `{{run:ID}}`, `{{stamp:kind:text}}`, `{{diagram:NAME}}`, `{{strips:SET}}`, `{{key:SET}}`, `{{kb:path}}` (file size), `{{n}}` (plate number).

## Bench slot (for the interactive benches)

Each project page has a slot built by `pages.project_page()`:

```html
<section class="bench" data-bench="tripline" aria-label="Recorded readings">
  <figure class="plate">
    <span class="plate-label">Plate 1</span>
    <div class="bench-static"> ...recorded static state, real data, works without JS... </div>
    <div class="bench-live" data-bench-mount hidden></div>
    <figcaption>claim the plate supports</figcaption>
  </figure>
</section>
```

Convention for a bench module:

1. Create `assets/js/bench-NAME.js` (NAME is the project slug). `build.py` adds `<script type="module" src="/assets/js/bench-NAME.js"></script>` to that page only, and only when the file exists. Module scripts are deferred; no other page loads it.
2. The module finds `document.querySelector('[data-bench="NAME"]')`, builds its UI inside `.bench-live` (it may `fetch('/assets/data/bench-NAME.json')`), then sets `hidden` on `.bench-static` and removes it from `.bench-live`. If anything fails, leave `.bench-static` visible. Never depend on the static region being absent.
3. The static region is the recorded state and must stay complete and correct on its own. Replace the placeholder content in `content/NAME.html` (`<!--@bench-->`) with the real recorded table when the data is captured.
4. Budget: at most 9 KB gzipped including data. Respect `prefers-reduced-motion` (no tweening), expose results in an `aria-live="polite"` region, keep full keyboard operation, and add a parity test that fails the build if the JS result differs from the captured tool output.
5. Put data in `assets/data/bench-NAME.json` with provenance (tool version, command, date, commit or run) and extend `scripts/check_facts.py` to validate its headline numbers.

### Worked example: sinkline "Sanitizer switch"

`data-bench="sinkline"`. A radio group picks the bug class (SQL, command, XSS) and another the version of the code (unsafe, right-class sanitizer, wrong-class sanitizer). The code pane marks lines that differ from the unsafe file with `+` and tags lines on the recorded path (source, propagate, sanitizer, sink); the output pane is the verbatim `sinkline scan` output, with a verdict stamp (text, not colour) and exit status. A visually hidden `role="status"` paragraph announces each change. The module (`model()` is pure, `mount(doc, root, data)` takes the document) fetches the JSON and, if that fails, leaves the static record visible. `scripts/bench_static.py` renders the same nine runs for the no-JS record. Provenance (tool version, tag, commit, command, date) is in the data file and the caption. `scripts/capture_sinkline_bench.py --sinkline PATH --check` re-runs the real CLI and fails if any stored capture differs; `node scripts/test_bench_sinkline.mjs` asserts that what the live bench and the static page display equals the stored captures. To update after a sinkline release: run the capture script without `--check`, then `python scripts/build.py`, then both checks.

## Motion

Only: strip entrance (CSS, scroll-driven, optional), one cross-document view transition (`@view-transition { navigation: auto }`; the strip pair on a card in `/projects/` morphs into the one on the project page through `view-transition-name: strip-SLUG`, set by `.vt` with a `--vt` custom property), and a 120 ms colour change on theme switch. All sit inside `prefers-reduced-motion: no-preference`; under `reduce` animations, transitions and the view-transition name are off. Unsupported browsers see the complete page.

## Print and forced colors

Print forces the light tokens, hides navigation, benches and buttons, and prints URLs after external links. `forced-colors` keeps strip shapes with `CanvasText` borders and a 2 px outline on missed ticks.

## Budgets (measured, see QC.md section 8)

CSS 26.6 KB raw / 6.9 KB gzip; global JS 1.9 KB raw / 0.8 KB gzip; fonts 81 KB (serif 51, mono 15 + 16); first load per page (HTML, CSS, JS, three fonts, gzip, no screenshots) 90 to 98 KB; no third-party requests.
