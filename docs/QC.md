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
