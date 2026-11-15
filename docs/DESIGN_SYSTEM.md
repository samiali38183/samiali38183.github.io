# Design

Direction: minimalist technical editorial. One column, a large serif name and one-sentence headline, small monospace labels, hairline rules. Figures are real: result images from the project repositories and recorded-data readings on the project pages. Each figure carries a label that says what the data is (recorded, benchmark, synthetic, real scan).

## Type and colour
- Source Serif 4 (text and display) and IBM Plex Mono (labels, code, figures), both OFL, self-hosted in `assets/fonts/`.
- Warm off-white paper, near-black ink, one link blue. Red and green appear only inside verdict stamps on project pages. Dark mode follows the operating system; there is no toggle.
- Body text is at least 17 px, contrast at least 4.5:1.

## Pages
- Home: name, headline, school and internship, resume and GitHub links, intro (30 to 60 words), four featured projects (25 to 50 word blurb and one real figure each), experience, additional research, education and certifications, contact.
- Work archive (`/projects/`): the remaining projects.
- Project pages: a 150 to 300 word overview and figure first. The recorded-data bench, the before and after record, how it works, limits and CI links follow, with long tables and code folded.
- About (100 to 150 words), Experience and education, Resume.

`scripts/build.py` asserts the word counts above. Copy lives in `scripts/pages.py` (home, about text) and `content/data/projects.json` (blurbs, overviews, Open Graph text).

## Open Graph
`python scripts/og/make_og.py` renders `assets/og/<project>.png` and `assets/og/home.png` with headless Chrome. The cards are text only, set from the project's own headline figure.

## JavaScript
Optional. `assets/js/site.js` adds the Copy button and opens folded sections for anchor links. The project benches (`assets/js/bench-*.js`) enhance static tables that are already in the page.
