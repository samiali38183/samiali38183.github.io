#!/usr/bin/env python3
"""Build the site: wrap page bodies with the shared header, footer and meta tags.

Usage: python scripts/build.py
Reads content/*.html (prose), content/data/*.json (project data, CI run states) and writes <path>/index.html for
every page, the redirect stubs, 404.html, sitemap.xml and robots.txt. Python 3 standard library only.
The generated files are committed, so the site needs no build step to serve.

Layout of the generator:
  scripts/build.py       page registry, layout (head, header, footer), redirects, sitemap
  scripts/pages.py       home, projects index and project-page bodies
  scripts/components.py  ruler strips, stamps, evidence chips, diagrams, table labels
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import components as C  # noqa: E402
import pages as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://samiali38183.github.io"
OG_IMAGE = BASE + "/assets/og.png"
OG_ALT = "A reading of 0 over 36 and two ruler strips: all 36 ticks outline or hatched as found, 2 filled as left."

# (url path, nav key, title, description, kind, argument)
PAGES = [
    ("/", "home", "Sami Ali | Security tools, checked against what they claim",
     "Sami Ali, George Mason University class of 2028. Detection, application-security and vulnerability-management tools, each checked against a reference, with the readings and CI runs.",
     "home", None),
    ("/projects/", "projects", "Projects | Sami Ali",
     "Seven projects, each checked against a reference: tripline, sinkline, kevgate, kevgate-admit, vulnlab, fuzzdiff and kev-risk-prioritization, with readings, limits and CI evidence.",
     "projects", None),
] + [
    (f"/projects/{slug}/", "projects", None, None, "project", slug)
    for slug in ["tripline", "sinkline", "kevgate", "kevgate-admit", "vulnlab", "fuzzdiff", "kev-risk-prioritization"]
] + [
    ("/experience/", "experience", "Experience | Sami Ali",
     "DHS HS-POWER intern on CBP's Vulnerability Assessment Team, May to August 2026. Education and certifications.",
     "content", "experience.html"),
    ("/about/", "about", "About | Sami Ali",
     "Student at George Mason University focused on detection engineering, application security and vulnerability management, and on checking that security tooling does what it says.",
     "content", "about.html"),
    ("/resume/", "resume", "Resume | Sami Ali",
     "Download Sami Ali's resume (PDF), Security Engineering and Red Team versions, with the same facts as text.",
     "content", "resume.html"),
]

NAV = [("projects", "/projects/", "Work"), ("experience", "/experience/", "Experience"),
       ("about", "/about/", "About"), ("resume", "/resume/", "Resume")]

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#F3EFE6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14161A" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sami Ali">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{ogalt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og}">
<meta name="twitter:image:alt" content="{ogalt}">
<link rel="preload" href="/assets/fonts/source-serif-4-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css">
{headextra}<script>try{{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap head-row">
<a class="brand" href="/">Sami Ali</a>
<nav class="site-nav" aria-label="Primary">
<ul>
{nav}
<li><button type="button" id="theme" aria-pressed="false" hidden>Dark mode</button></li>
</ul>
</nav>
</div>
{sheetline}
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-footer">
<div class="wrap">
<ul>
<li><a href="mailto:samiali38183@gmail.com">samiali38183@gmail.com</a></li>
<li><a href="https://github.com/samiali38183">GitHub</a></li>
<li><a href="https://www.linkedin.com/in/sami-ali-1a4b89345">LinkedIn</a></li>
<li><a href="/resume.pdf">Resume (PDF)</a></li>
</ul>
<p>Static site, no tracking, no cookies. Source: <a href="https://github.com/samiali38183/samiali38183.github.io">samiali38183.github.io</a>.</p>
</div>
</footer>
<script src="/assets/js/site.js" defer></script>
{extra}</body>
</html>
"""

REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved | Sami Ali</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={path}">
</head>
<body>
<p>This page moved to <a href="{path}">{url}</a>.</p>
</body>
</html>
"""

# old path -> new path
REDIRECTS = {
    "about.html": "/about/",
    "projects.html": "/projects/",
    "services.html": "/",
    "contact.html": "/about/",
    "projects/kev.html": "/projects/kev-risk-prioritization/",
    "projects/power-bi.html": "/experience/",
    "projects/agent-lab.html": "/projects/",
    "projects/call-kettle.html": "/projects/",
    "projects/phishing-ioc.html": "/projects/",
    "projects/wireshark.html": "/projects/",
}


def load_ctx() -> dict:
    return {
        "projects": json.loads((ROOT / "content/data/projects.json").read_text(encoding="utf-8")),
        "runs": json.loads((ROOT / "content/data/runs.json").read_text(encoding="utf-8")),
    }


def number_plates(body: str) -> str:
    """Replace each {{n}} with 1, 2, 3 ... in document order."""
    count = iter(range(1, 100))
    return re.sub(r"\{\{n\}\}", lambda _m: str(next(count)), body)


def render(ctx: dict, kind: str, arg: str | None, path: str) -> tuple[str, str, str, str, str]:
    """Return (title, description, body, sheetline, extra scripts) for one page."""
    extra = ""
    sheetline = ""
    if kind == "home":
        body = P.home(ctx)
    elif kind == "projects":
        body = P.projects_index(ctx)
    elif kind == "project":
        p = ctx["projects"]["projects"][arg]
        body = P.project_page(ctx, arg)
        sheetline = (f'<p class="wrap sheetline"><b>Sheet {p["sheet"]} of {len(ctx["projects"]["order"])}</b> &middot; {html.escape(p["name"])}'
                     f' &middot; {html.escape(p["version"] if p["version"].startswith("v") else "main")}</p>')
        bn = p.get("bench", arg)
        if (ROOT / "assets/js" / f"bench-{bn}.js").exists():
            extra = f'<script type="module" src="/assets/js/bench-{bn}.js"></script>\n'
    else:
        body = P.expand(ctx, (ROOT / "content" / arg).read_text(encoding="utf-8").strip())
    body = body.replace('<aside class="note">', '<div class="note" role="note">').replace('</aside>', '</div>')
    body = C.label_tables(number_plates(body))
    title = desc = ""
    return title, desc, body, sheetline, extra


def build() -> None:
    ctx = load_ctx()
    nav_cache = {}
    for path, key, title, desc, kind, arg in PAGES:
        _, _, body, sheetline, extra = render(ctx, kind, arg, path)
        if kind == "project":
            p = ctx["projects"]["projects"][arg]
            title, desc = p["title"], p["desc"]
        nav = "\n".join(
            '<li><a href="{}"{}>{}</a></li>'.format(
                href, (' aria-current="page"' if path == href else ' aria-current="true"') if k == key else "", label)
            for k, href, label in NAV)
        headextra = ""
        bn = ctx["projects"]["projects"][arg].get("bench", arg) if kind == "project" else arg
        if kind == "project" and (ROOT / "assets/css" / f"bench-{bn}.css").exists():
            headextra = f'<link rel="stylesheet" href="/assets/css/bench-{bn}.css">\n'
        out = LAYOUT.format(
            headextra=headextra, title=html.escape(title), desc=html.escape(desc, quote=True), canon=BASE + path, og=OG_IMAGE,
            ogalt=html.escape(OG_ALT, quote=True), nav=nav, body=body, sheetline=sheetline, extra=extra)
        target = ROOT / path.strip("/") / "index.html" if path != "/" else ROOT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8", newline="\n")
        nav_cache[path] = nav

    nav404 = "\n".join('<li><a href="{}">{}</a></li>'.format(h, lab) for _, h, lab in NAV)
    body404 = P.expand(ctx, (ROOT / "content" / "404.html").read_text(encoding="utf-8").strip())
    nf = LAYOUT.format(headextra="", title="Page not found | Sami Ali", desc="Page not found.", canon=BASE + "/404.html", og=OG_IMAGE,
                       ogalt=html.escape(OG_ALT, quote=True), nav=nav404, body=body404, sheetline="", extra="")
    nf = nf.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"')
    (ROOT / "404.html").write_text(nf, encoding="utf-8", newline="\n")

    for old, new in REDIRECTS.items():
        (ROOT / old).write_text(REDIRECT.format(path=new, url=BASE + new), encoding="utf-8", newline="\n")

    urls = "".join(f"<url><loc>{BASE}{p}</loc></url>\n" for p, *_ in PAGES)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n",
        encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n",
                                     encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
    print("built", len(PAGES), "pages and", len(REDIRECTS), "redirects")
