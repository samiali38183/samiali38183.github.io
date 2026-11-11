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
