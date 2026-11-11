# samiali38183.github.io

Portfolio of Sami Ali. Live at https://samiali38183.github.io/

Plain HTML and CSS, one shared stylesheet (`assets/css/site.css`), a small optional script (theme toggle, copy buttons). No framework, no tracking, no external requests. It works with JavaScript disabled. Design system: `docs/DESIGN_SYSTEM.md`.

- `content/` holds the prose and `content/data/` the project data; `scripts/build.py` (with `pages.py` and `components.py`) generates the pages and wraps them with the shared header, footer and meta tags, and writes the redirect pages, `sitemap.xml` and `robots.txt`. The generated HTML is committed, so serving the site needs no build step. Edit `content/`, then run `python scripts/build.py`.
- `scripts/check_facts.py` re-derives the numbers shown on the site from the project repos and GitHub. `docs/QC.md` records the last verification run.
- `resume.pdf` (Security Engineering) and `resume-red-team.pdf`; `assets/certs/` holds certificate PDFs.
- The old terminal-style portfolio was removed; it is in the git history.
