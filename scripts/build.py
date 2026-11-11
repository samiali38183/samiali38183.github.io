#!/usr/bin/env python3
"""Wrap the page bodies in content/ with the shared header, footer and meta tags.

Usage: python scripts/build.py
Writes <path>/index.html for every page, the redirect stubs, sitemap.xml and robots.txt.
No dependencies. The generated files are committed, so the site needs no build step to serve.
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://samiali38183.github.io"

# (url path, nav key, title, description, content file)
PAGES = [
    ("/", "home", "Sami Ali | Security engineering student",
     "Sami Ali, George Mason University. Detection, application-security and vulnerability-management tooling, with measured results and public code.",
     "home.html"),
    ("/projects/", "projects", "Projects | Sami Ali",
     "Three security tools with test counts, benchmarks and CI evidence: tripline (detection gate), sinkline (taint analyzer), kevgate (vulnerability intake service).",
     "projects.html"),
    ("/projects/tripline/", "projects", "tripline: a CI gate for detection rules | Sami Ali",
     "tripline replays recorded ATT&CK telemetry through Sigma rules on every pull request. The stock SigmaHQ setuid rule matched 0 of 36 events.",
     "tripline.html"),
    ("/projects/sinkline/", "projects", "sinkline: taint analysis for Python web apps | Sami Ali",
     "sinkline follows request data across functions and files to dangerous sinks. 91 tests; F1 0.992 on a 109-line self-labeled benchmark.",
     "sinkline.html"),
    ("/projects/kevgate/", "projects", "kevgate: KEV-ranked vulnerability intake | Sami Ali",
     "kevgate ranks scanner findings by CISA KEV, EPSS, CVSS and asset criticality. 277 tests, hashed scoped API keys, and CI that tests NetworkPolicy and Pod Security on kind.",
     "kevgate.html"),
    ("/projects/kevgate-admit/", "projects", "kevgate-admit: Kubernetes admission webhook | Sami Ali",
     "kevgate-admit is a Go admission webhook that denies or warns on workloads whose image digests carry KEV-listed or over-threshold vulnerabilities. 72 tests, 95% coverage, kind end-to-end run in CI.",
     "kevgate-admit.html"),
    ("/projects/fuzzdiff/", "projects", "fuzzdiff: picohttpparser in safe Rust | Sami Ali",
     "fuzzdiff ports the picohttpparser HTTP parser from C to safe Rust and checks it against the original with differential tests, property tests, seeded bugs and libFuzzer.",
     "fuzzdiff.html"),
    ("/projects/kev-risk-prioritization/", "projects", "kev-risk-prioritization | Sami Ali",
     "A small standard-library script that ranks scan findings with KEV status first, run on a 20-finding synthetic sample.",
     "kev-risk.html"),
    ("/experience/", "experience", "Experience | Sami Ali",
     "DHS HS-POWER intern on CBP's Vulnerability Assessment Team, May to August 2026. Education and certifications.",
     "experience.html"),
    ("/about/", "about", "About | Sami Ali",
     "Student at George Mason University focused on detection engineering, application security and vulnerability management.",
     "about.html"),
    ("/resume/", "resume", "Resume | Sami Ali",
     "Download Sami Ali's resume (PDF), Security Engineering and Red Team versions, with the same facts as text.",
     "resume.html"),
]

NAV = [("projects", "/projects/", "Projects"), ("experience", "/experience/", "Experience"),
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
<meta name="theme-color" content="#0a58ad">
<meta property="og:type" content="{ogtype}">
<meta property="og:site_name" content="Sami Ali">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap">
<a class="brand" href="/">Sami Ali</a>
<nav class="site-nav" aria-label="Main">
<ul>
{nav}
<li><button type="button" id="theme" hidden>Dark theme</button></li>
</ul>
</nav>
</div>
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
<script src="/site.js" defer></script>
</body>
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


# Architecture diagrams: vertical flows so they stay readable at phone width.
DIAGRAMS = {
    "fuzzdiff": ("fuzzdiff differential harness", "Fuzzer or test bytes are decoded into a case. The same case runs through the C original, which is compiled with sanitizers and fed exact-size heap copies, and through the safe Rust port. The harness compares the two results and classifies them as Equal, BothReject, RustStricter or Divergence.", [
        ("box", "Input bytes", "corpus, generator, proptest, libFuzzer"),
        ("box", "Decode into a case", "entry point, header capacity, last_len, chunk splits"),
        ("box", "C original and Rust port, same case", "C: exact-size heap copy, ASan/UBSan; Rust: safe"),
        ("hi", "compare()", "consumed length, fields, decoded bytes"),
        ("box", "Equal, BothReject, RustStricter (D1, D2)", "expected outcomes"),
        ("warn", "Divergence", "a bug in one side; fails tests and the CI fuzz job"),
    ]),
    "kevgate-admit": ("kevgate-admit admission path", "The API server posts an AdmissionReview over TLS. The webhook decodes it and extracts every image, parses each reference by digest, looks up a vulnerability report per digest with time and size limits, scores findings and applies the namespace policy, then allows, warns or denies.", [
        ("box", "kube-apiserver", "AdmissionReview v1 over TLS, CREATE and UPDATE"),
        ("box", "Strict decode, extract images", "containers, init, ephemeral; at most 128 images"),
        ("box", "Parse references by digest", "tags are never resolved"),
        ("hi", "Bounded evidence lookup", "Trivy report per digest; timeouts, concurrency cap"),
        ("box", "Score and apply namespace policy", "kevgate risk model; policy hot-reloaded"),
        ("warn", "Allow, warn (audit mode) or deny", "message names the rule and top findings"),
    ]),
    "tripline": ("tripline data flow", "Recorded telemetry is committed as fixtures, Sigma rules are compiled to Python predicates, a logsource router decides which events each rule sees, and the scorer fails the build if an expected rule misses.", [
        ("box", "Emulate and record", "Atomic Red Team on CI runners; public AWS logs"),
        ("box", "Fixtures committed to the repo", "run.ndjson + manifest.json, reviewed by a person"),
        ("box", "Compile Sigma rules to predicates", "pySigma parses; tripline walks the condition tree"),
        ("box", "Logsource router", "a rule only sees events its logsource matches"),
        ("hi", "Replay and score per scenario", "weights from technique prevalence"),
        ("warn", "Gate: exit 1 if an expected rule misses", "scorecard, JUnit, ATT&CK Navigator layer, HTML"),
    ]),
    "sinkline": ("sinkline analysis passes", "Python files are parsed and names resolved. Pass 1 computes a summary per function to a fixpoint. Pass 2 re-runs with real sources and uses the summaries at each call site. Findings come out as text, JSON, SARIF or HTML.", [
        ("box", "Parse and resolve names", "ast, imports, aliases, receiver types"),
        ("box", "Pass 1: function summaries", "parameters as labels, repeated to a fixpoint"),
        ("box", "Pass 2: real sources", "request data enters; summaries used at call sites"),
        ("hi", "Taint with CWE-scoped sanitizers", "join: union of labels, intersect cleared CWEs"),
        ("box", "Sink match", "keyword gates, receiver types, CWE not cleared"),
        ("warn", "Report with the source-to-sink path", "text, JSON, SARIF 2.1.0, HTML"),
    ]),
    "kevgate": ("kevgate request path and delivery pipeline", "A request passes request-context and body-size middleware, then a scope check with a per-key rate limit, then scoring and SQLite storage. Separately, CI builds the image, scans it, deploys it to kind and tests the network and pod-security controls.", [
        ("box", "Scanner or analyst, Bearer key", "JSON or Nessus/Tenable CSV in, ranked queue out"),
        ("box", "Middleware", "request id, JSON log, metrics, 1 MiB body limit"),
        ("hi", "Auth and rate limit", "constant-time key check, scopes, token bucket"),
        ("box", "Scoring and repository", "KEV, EPSS, CVSS, ACR; parameterised SQL on SQLite"),
        ("box", "CI: build, scan, sign", "Semgrep, Bandit, pip-audit, gitleaks, Trivy, cosign"),
        ("warn", "CI: kind with Calico", "NetworkPolicy, Pod Security restricted, ZAP baseline"),
    ]),
}


def diagram(key: str) -> str:
    title, desc, boxes = DIAGRAMS[key]
    w, bh, gap, x, bw = 440, 54, 26, 20, 400
    h = len(boxes) * bh + (len(boxes) - 1) * gap + 8
    out = [f'<figure class="diagram"><svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="{key}-t {key}-d">',
           f'<title id="{key}-t">{html.escape(title)}</title><desc id="{key}-d">{html.escape(desc)}</desc>']
    for i, (kind, a, b) in enumerate(boxes):
        y = 4 + i * (bh + gap)
        out.append(f'<rect class="{kind}" x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6"/>')
        out.append(f'<text x="{w // 2}" y="{y + 22}" text-anchor="middle" font-weight="600">{html.escape(a)}</text>')
        out.append(f'<text class="sub" x="{w // 2}" y="{y + 41}" text-anchor="middle">{html.escape(b)}</text>')
        if i < len(boxes) - 1:
            y1, y2 = y + bh, y + bh + gap
            out.append(f'<line class="arrow" x1="{w // 2}" y1="{y1}" x2="{w // 2}" y2="{y2 - 6}"/>')
            out.append(f'<path class="head" d="M{w // 2 - 5} {y2 - 7} L{w // 2 + 5} {y2 - 7} L{w // 2} {y2} Z"/>')
    out.append("</svg>")
    out.append(f"<figcaption>{html.escape(desc)}</figcaption></figure>")
    return "".join(out)


def build() -> None:
    for path, key, title, desc, fname in PAGES:
        body = (ROOT / "content" / fname).read_text(encoding="utf-8").strip()
        for k in DIAGRAMS:
            body = body.replace("{{diagram:%s}}" % k, diagram(k))
        nav = "\n".join(
            '<li><a href="{}"{}>{}</a></li>'.format(
                href, ' aria-current="page"' if k == key else "", label)
            for k, href, label in NAV)
        out = LAYOUT.format(
            title=html.escape(title), desc=html.escape(desc, quote=True),
            canon=BASE + path, ogtype="website", nav=nav, body=body)
        target = ROOT / path.strip("/") / "index.html" if path != "/" else ROOT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8", newline="\n")

    nav404 = "\n".join('<li><a href="{}">{}</a></li>'.format(h, lab) for _, h, lab in NAV)
    nf = LAYOUT.format(title="Page not found | Sami Ali", desc="Page not found.", canon=BASE + "/404.html",
                       ogtype="website", nav=nav404,
                       body=(ROOT / "content" / "404.html").read_text(encoding="utf-8").strip())
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
