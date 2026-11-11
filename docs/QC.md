# QC record

Verification of the redesign, run on 2026-11-10 and 2026-11-11 before the merge (against `python -m http.server` on the working tree) and again against the live site after deploy (section at the end).

## 1. Layout (headless Chrome, 360, 390, 768, 1280 px)

All 10 pages (home, projects index, 5 project pages, experience, about, resume) plus 404 were loaded in headless Chrome through puppeteer-core at 360, 390, 768 and 1280 px, in light and dark color schemes (88 page views), and screenshots were viewed for 390 and 1280 px. Findings fixed during the pass: diagram text too small on phones (larger type, shorter labels), copy button overlapping the first line of code blocks, missing space above the "All projects" link. Result: no horizontal page overflow at any width (`scrollWidth <= innerWidth` checked on every view); diagrams, tables and code blocks scroll or scale inside their own box.

## 2. Links and files

`python scripts/check_links.py` (internal links, `src`, `href`, anchors, meta-refresh targets, then every external URL with GET): 185 internal references resolved, 47 unique external URLs, all 2xx or 3xx except `https://www.linkedin.com/in/sami-ali-1a4b89345`, which returns 999 to bots (recorded as bot-blocked, not broken). Canonical and Open Graph URLs on the live domain are checked against the working tree before deploy.

Resume PDFs: `resume.pdf` is byte-identical to `Sami_Ali_Resume_SecurityEngineering.pdf` and `resume-red-team.pdf` to `Sami_Ali_Resume_RedTeam.pdf` (both from the vault's `17-Resume-Package`); each is 1 page with extractable text (3604 and 3753 characters). Certificate PDFs in `assets/certs/` are 1 page each and extract.

## 3. Validation, accessibility, console

- `html-validate` 11.21.0 (recommended ruleset) on every generated HTML file: 0 errors, exit code 0. Fixes during the pass: uppercase DOCTYPE, titles over 70 characters, `th` scope attributes, scrollable table wrappers as `section` elements.
- axe-core (puppeteer, tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa, best-practice) on 11 pages x 4 widths x 2 color schemes: 0 violations of any impact, including color contrast and scrollable-region-focusable.
- Console: no console errors or warnings, page errors, failed requests or HTTP responses of 400 or above on any page view.
- Lighthouse was not run. Keyboard use (skip link, visible focus ring, tab order, scrollable code and tables focusable) was reviewed by hand and by the axe rules above; the site works with JavaScript disabled (the theme button stays hidden and copy buttons are absent).
- Size: HTML + `styles.css` + `site.js` per page between 14 KB and 29 KB (largest: kevgate, 28.6 KB). Screenshots are 28 KB and 13 KB PNGs, lazy loaded. No external requests.

## 4. Fact check

`python scripts/check_facts.py --clones <dir> ...` re-derives numbers from fresh clones and GitHub, and compares them with the page text: latest release tags (GitHub API), tripline scorecard totals and `tripline replay --all` output, the 0-of-36 and 2-of-36 setuid counts (replayed through tripline's own API), pytest collection counts (tripline 186, sinkline 91, kevgate 277, kev-risk-prioritization 9), sinkline `bench/score.py` and `bench/compare_bandit.py` output and `sinkline rules` totals, kev-risk sample statistics, kevgate-admit `go test` counts (72 top-level, 308 total), coverage (95.0%) and the 1000 parity vectors, and the conclusion of every GitHub Actions run URL on the site. Result: 46 passed, 0 failed.

Mismatches and notes found:

- tripline: the committed `docs/img/report.png` is stale (shows 47%, 7 of 14 scenarios from v0.2.0) and the README embeds it; the live Pages report is current (68%, 10 of 14). The site uses a screenshot of the live report.
- tripline: the two emulation runs that the repo cites as telemetry sources (41838714456 Linux, 42917025570 Windows) show as failed on GitHub because their final assertion step failed. The site says so instead of presenting them as green.
- kevgate: tag `v0.1.0` points at the merge of PR #1 (`8324f04`); the hardening PR #2 (277 tests) is on `main` after the tag. The site states this.
- sinkline benchmark HTML report shows 71 findings, more than the 60 benchmark true positives, because it also covers `smoke_app.py`, which `bench/score.py` skips. The site says so.

## 5. Copy

Spell-checked all page text (pyspellchecker) and read every page: only product names and technical terms were flagged. Banned-phrase grep (leverage, robust, cutting-edge, seamless, empower, passionate, journey, "in today", AI-assistance wording, clearance) returns nothing. About page: 167 words.

## 6. Live site (after deploy, 2026-11-11)

Pages build for merge commit `ff40cc5` finished with status `built` and no error.

- `python scripts/check_links.py https://samiali38183.github.io`: 147 internal references fetched with HTTP 200 and anchors found, 39 unique external URLs 2xx or 3xx except LinkedIn (999, bot-blocked). Result OK.
- Resume and certificate PDFs downloaded from the live site: `resume.pdf` and `resume-red-team.pdf` return 200 as `application/pdf`, 1 page each, text extractable, byte-identical to the repository files; the two certificate PDFs are the same.
- Old URLs (`about.html`, `projects.html`, `services.html`, `contact.html`, `projects/kev.html`, `projects/power-bi.html`) return 200 and carry a meta refresh plus canonical to the new page. An unknown path returns the 404 page with status 404.
- The puppeteer and axe run repeated against the live URLs (88 page views): 0 axe violations, no horizontal overflow, no console errors or failed requests.

## 7. fuzzdiff page added (2026-11-11)

Added `/projects/fuzzdiff/`, a fifth entry on the projects index and a one-line mention on the home page. Checks re-run on the branch before merge:

- `scripts/check_facts.py` extended for fuzzdiff and re-run: 58 passed, 0 failed. New checks: `cargo test --all` total (29), seeded-bug detection counts (3, 286, 8 inputs) and the 500,000-input control, line coverage of `src/` from `cargo llvm-cov` (95.88%), the three libFuzzer execution counts parsed from the log of fuzz run 42961733885, and the conclusion of the three fuzzdiff CI runs linked on the page.
- Browser checks (puppeteer + axe, 12 pages x 4 widths x 2 color schemes = 96 views): 0 axe violations, no horizontal overflow, no console errors or failed requests.
- `html-validate`: 0 errors. `scripts/check_links.py`: 200 internal references and 58 unique external URLs, all fine except LinkedIn (bot-blocked).
- The resume PDFs were not touched in this change.
- Not re-run locally: libFuzzer and the sanitizer jobs (Linux CI only; numbers come from the CI logs) and the benchmarks (one-machine numbers from `docs/BENCHMARKS.md`).

## 8. Visual identity redesign (branch `redesign/identity`, 2026-11-11)

New design system ("As Found / As Left", see `docs/DESIGN_SYSTEM.md`), a generator extended with strips, stamps, chips and a project template, and all 11 pages migrated.

- **Layout** (headless Chrome via puppeteer-core, `chrome.exe` from Program Files): 12 pages (home, projects index, 6 project pages, experience, about, resume, 404) at 360, 390, 768, 1280 and 1600 px in light and dark = 120 page views; screenshots were viewed and fixed (strip tick labels colliding with the value line, label column wasting phone width, 5- and 7-column ledgers overflowing at 768 px, chips overflowing at 360 px, heading order on the projects index, landmarks without names). Result: no horizontal overflow at any width (`scrollWidth <= innerWidth` on every view).
- **html-validate** 11.21.0 (recommended ruleset), 12 generated pages: 0 errors. Fixed: `details` placed before `figcaption`, unnamed landmarks (margin notes are `role="note"` divs).
- **axe-core** (tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa, best-practice), 120 page views: 0 violations, including contrast in both themes.
- **Console and network**: no console errors or warnings, page errors, failed requests or HTTP 400+ responses on any view. No third-party requests (3 fonts, 1 stylesheet, 1 script, favicon, plus images on pages that have them).
- **Links**: `python scripts/check_links.py`: 227 internal references, 63 unique external URLs, all fine except LinkedIn (999, bot-blocked). Result OK.
- **Facts**: `python scripts/check_facts.py --clones ... ` against fresh clones at the commits shown on each page and live GitHub runs: 59 passed, 0 failed. Needles updated for the new home and resume text (0 of 36 on home, `vs 0.579` on home, kevgate 277 on the resume page). The admit-webhook transcript count (5 outcomes) was read from the README, not scripted.
- **Sizes** (gzip, HTML + CSS + JS + three fonts, excluding screenshots): 90 to 98 KB per page. CSS 26.6 KB raw / 6.9 KB gzip, global JS 1.9 KB / 0.8 KB, fonts 81 KB, Open Graph image 14 KB. HTML raw: 3 to 38 KB; tripline (31 KB) and sinkline (38 KB) exceed the 30 KB raw target, all pages are under 10 KB gzip.
- **Not verified**: Lighthouse and real-device performance numbers; cross-document view transition and scroll-driven strip entrance in a browser other than Chrome; forced-colors and print previews were not rendered; screen-reader output was not listened to.

## 9. tripline Rule bench (branch `bench/tripline`, 2026-11-11)

- **Parity (ground truth from tripline itself).** `scripts/gen_bench_tripline.py` installs nothing; run it with a Python that has tripline 0.2.1 installed from a clone of `main` (commit 5da08bb). It builds synthetic auditd-style events (`type: EXECVE`, `Image`, `CommandLine`) and evaluates both rules with `tripline.engine.rules.evaluate`, tripline's own Sigma compiler. Cases: 14 presets, the 36 applicable events of `fixtures/linux/t1548-001-setuid-setgid/run.ndjson`, and 300 seeded random chmod-like strings (octal and symbolic modes, clause lists, `-R`/`--` options, full paths, `/usr/share/doc/` operand variants, tabs, newlines, Unicode spaces, upper case, `chown root` shapes, odd Images). Result stored in `assets/data/tripline-bench-parity.json` with per-condition booleans and the reason text. The generator also asserts that Python `re` on the YAML patterns combines to the compiler's verdict for every case.
- **`node scripts/test_bench_tripline.mjs`** (Node 24.15): 350 cases, 0 differences in conditions, verdicts and reason text (preset 14, fixture 36, random 300); the 36 recorded events carry stock 0 and replacement 2. Python `re` and JavaScript `RegExp` differ on `\s`, `\w` and `$`, so the bench translates those three before compiling; a mutation check (naive `new RegExp(pattern)`) fails 19 of the 300 random cases, so the random set does exercise those differences. Not covered: input longer than 300 characters (the field is capped), and Python-only regex syntax in a future rule edit (the generator would need to be rerun and the test would fail if the translation broke).
- **Data**: `assets/data/bench-tripline.json` 4.8 KB (1.1 KB gzip): rule patterns copied from the YAML, 14 presets, 36 events (image and command line trimmed to 110 characters, verdicts). Only those fields; no environment, user, host or session data. The generator fails if an event text matches a secret-looking pattern; the two long events are the `pwsh Invoke-AtomicTest` lines, which contain only the public GUIDs. `scripts/check_facts.py` now checks the patterns against the YAML in the clone, the 36 / 0 / 2 totals, and the parity count on the page.
- **Weight**: `bench-tripline.js` 11.6 KB raw, 4.3 KB gzip; `bench-tripline.css` 1.1 KB gzip; data 1.1 KB gzip; total 6.5 KB gzip against the 9 KB budget. Page HTML 10.0 KB gzip (it holds the complete static state: 14-row table and the 36-event table). Loaded on `/projects/tripline/` only.
- **Browser** (headless Chrome via puppeteer-core, `chrome.exe`): at 360 and 1280 px the bench replaces the static state, no horizontal overflow, no console errors. Scripted: typed `chmod g+w,u+s /tmp/x` (stock not flagged, replacement flagged, live status text updated), clicked the presets (`Doc path appended` flagged, `Only under /usr/share/doc/` excluded), clicked a bench tick and a tick in the reading band strips (both open the event; `Next event` advances), and loaded the page with JavaScript disabled (static table visible, bench hidden). Screenshots were viewed. Findings fixed: the reading-band click handler also matched the legend strips; heading order (visually hidden `h2` added before the bench `h3`s).
- **axe-core** (same tags as section 3, 12 pages x 4 widths x 2 schemes, live bench included): 0 violations. **html-validate** on `projects/tripline/index.html`: 0 errors.
- **Links**: `scripts/check_links.py`: 229 internal references, 66 unique external URLs; the only failure is the link to `scripts/test_bench_tripline.mjs` on `main` of this repository, which returns 404 until this branch is merged. LinkedIn is bot-blocked as before.
- **Numbers on the page** re-verified against the repository and `gh run list`: v0.2.1, 186 tests, 10 passed and 4 pending, 68% weighted; unchanged, so no number was edited. Latest `ci` run on `main` is green (42991181908 for a dependency update; the page keeps run 42957008252 for the commit its numbers were measured at).
- **Not verified**: screen-reader output was not listened to; keyboard use was exercised through the select and buttons, not by recorded key events; the ticks themselves are pointer-only by design (the select and Previous/Next buttons are the keyboard path, so that no 24 px target rule is broken by 36 adjacent ticks).
