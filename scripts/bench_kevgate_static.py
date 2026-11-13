"""Static (no-JS) record of the kevgate "Control to evidence matrix", the figure caption and the deployment architecture figure.

All three are generated from assets/data/kevgate-bench.json, which scripts/capture_kevgate_bench.py writes from kevgate v0.1.1 and
from real CI runs. This module only formats it. The live bench (assets/js/bench-kevgate.js) shows the same strings one control at a
time; scripts/test_bench_kevgate.mjs checks that the page and the module display exactly the stored data.
"""
from __future__ import annotations

import json
from html import escape as esc
from pathlib import Path

import components as C

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data" / "kevgate-bench.json"

# Same wording as KINDS in assets/js/bench-kevgate.js
KINDS = {
    "https://cyclonedx.org/bom": "SBOM (CycloneDX)",
    "https://sigstore.dev/cosign/sign/v1": "signature (cosign)",
    "https://slsa.dev/provenance/v1": "provenance (SLSA)",
}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def rich(text: str) -> str:
    """Escape, and turn the `backtick` spans of the repository's docs into <code>."""
    return "".join(f"<code>{esc(s)}</code>" if i % 2 else esc(s) for i, s in enumerate(text.split("`")))


def ref(d: dict, x: dict) -> tuple[str, str]:
    more = x["end"] > x["start"]
    text = f'{x["path"]}:{x["start"]}' + (f'-{x["end"]}' if more else "")
    href = f'{d["meta"]["repo"]}/blob/{d["meta"]["tag"]}/{x["path"]}#L{x["start"]}' + (f'-L{x["end"]}' if more else "")
    return text, href


def link(text: str, href: str) -> str:
    return f'<a href="{esc(href, quote=True)}">{esc(text)}</a>'


def doc_ref(d: dict, x: dict) -> tuple[str, str]:
    src = f'{x["src"]}, line {x["line"]}' + (f' ({x["stride"]})' if x.get("stride") else "")
    return src, f'{d["meta"]["repo"]}/blob/{d["meta"]["tag"]}/{x["src"]}#L{x["line"]}'


def quote(d: dict, x: dict) -> str:
    src, href = doc_ref(d, x)
    return f'<blockquote><p>{rich(x["text"])}</p></blockquote><p class="kg-src">Source: {link(src, href)}</p>'


def chip(d: dict, wf: str, ok: bool) -> str:
    r = d["runs"][wf]
    state, word = ("pass", "passed") if ok else ("fail", "failed")
    return (f'<a class="chip" data-s="{state}" href="{d["meta"]["repo"]}/actions/runs/{r["id"]}"><span class="st" aria-hidden="true"></span>'
            f'<span>run {r["id"]}</span> <span class="d">{word} {r["date"]}</span></a>')


def registry_text(d: dict, c: dict) -> str:
    g = c["registry"]
    kinds = ", ".join(KINDS.get(k, k) for k in g["attached"])
    return (f'Registry check on {d["meta"]["captured"]}: {g["image"]}:{g["tag"]} resolves, with an anonymous token and no credentials, to '
            f'{g["digest"]}. Attached to that digest: {kinds}. The SBOM lists {g["sbom_components"]} components; the SBOM and the provenance name that digest as their subject.')


def ci_item(d: dict, s: dict) -> str:
    r = d["runs"][s["wf"]]
    text = f'{s["wf"]} / {s["job"]} / step {s["n"]}: {s["step"]}'
    job = f'{d["meta"]["repo"]}/actions/runs/{r["id"]}/job/{s["job_id"]}'
    st, sh = ref(d, s["src"])
    out = f'{link(text, job)} {chip(d, s["wf"], s["conclusion"] == "success")}<br>Step defined at {link(st, sh)}'
    if s["asserts"]:
        out += "; asserts at " + ", ".join(link(*ref(d, a)) for a in s["asserts"])
    return f"<li>{out}</li>"


def test_item(d: dict, t: dict) -> str:
    text = f'{t["path"]}::{t["name"]}' + (f' ({t["cases"]} cases)' if t["cases"] > 1 else "")
    return f'<li>{link(text, ref(d, t)[1])}</li>'


def matrix_rows(d: dict) -> str:
    label = {x["id"]: x["label"] for x in d["layers"]}
    rows = []
    for c in d["controls"]:
        tests = ""
        if c["tests"]:
            tests = f'<p class="kg-eh">Tests</p><ul class="kg-list">{"".join(test_item(d, t) for t in c["tests"])}</ul>'
        ci = f'<ul class="kg-list">{"".join(ci_item(d, s) for s in c["ci"])}</ul>'
        reg = f'<p class="kg-src">{esc(registry_text(d, c))}</p>' if c.get("registry") else ""
        note = f'<p class="kg-src">{rich(c["note"])}</p>' if c.get("note") else ""
        rows.append(
            f'<tr data-control="{c["id"]}"><th scope="row"><span class="label">{esc(label[c["layer"]])}</span><br>{esc(c["title"])}</th>'
            f'<td>{quote(d, c["threat"])}</td>'
            f'<td><ul class="kg-list">{"".join("<li>" + link(*ref(d, x)) + "</li>" for x in c["code"])}</ul></td>'
            f'<td>{tests}<p class="kg-eh">CI steps</p>{ci}{reg}</td>'
            f'<td>{"".join(quote(d, x) for x in c["limits"])}{note}</td></tr>')
    return "".join(rows)


def kevgate_static() -> str:
    d = load()
    m = d["meta"]
    n = len(d["controls"])
    return (
        f'<p class="sw-lead">Recorded, not live. All {n} controls are listed here; with JavaScript on, a filter by layer and a detail panel replace this table.</p>'
        f'<div class="scroll wide"><table class="tbl wt kg-all"><caption>{n} controls of kevgate {esc(m["tag"])}: the threat each addresses, where it is implemented, '
        'the tests and CI steps that cite it, and its limitation</caption>'
        '<thead><tr><th scope="col">Control</th><th scope="col">Threat</th><th scope="col">Implemented at</th><th scope="col">Evidence</th>'
        '<th scope="col">Limitation</th></tr></thead><tbody>' + matrix_rows(d) + "</tbody></table></div>")


def kevgate_what() -> str:
    """Always visible: what the matrix is and what evidence means."""
    return (
        '<div class="kg-what"><p><b>What this is.</b> A map from each claim about a control to the code that implements it and to the checks that cite it. '
        'It does not evaluate anything in the browser, and it is not a test report: the results are the recorded state of the cited CI steps.</p>'
        '<p><b>What evidence means here.</b> A test or a CI step that asserts the behavior, and that passed in the run linked beside it. '
        'It is not an audit, and nothing was deployed to a real cloud account: the Kubernetes checks ran on a throwaway kind cluster, and the Terraform was never applied to AWS.</p></div>')


def kevgate_caption() -> str:
    d = load()
    m = d["meta"]
    n = len(d["controls"])
    steps = sum(len(c["ci"]) for c in d["controls"])
    return (
        f"<b>Every one of {n} controls cites at least one test or CI step; none of the cited tests or steps is evidence that the control is sufficient.</b> "
        f"Recorded, not live: every line number, test name, CI job and step comes from <code>{esc(m['tool'])}</code> {esc(m['tag'])} (commit {esc(m['commit'])}) "
        f"and from real GitHub Actions runs, captured on {esc(m['captured'])} with Python {esc(m['python'])} and pytest {esc(m['pytest'])}: "
        f"{m['tests_cited']} cited tests ({m['test_cases_cited']} cases, all passed on a rerun) of {m['tests_total']} collected, and {steps} CI step citations. "
        "The page evaluates nothing. Regenerate with <code>python scripts/capture_kevgate_bench.py</code>; "
        "<code>python scripts/capture_kevgate_bench.py --check</code> compares the stored data with a fresh capture and "
        "<code>node scripts/test_bench_kevgate.mjs</code> checks that the page shows exactly the stored data.")


# ---------------------------------------------------------------------------------------------------------------------
# Deployment architecture plate. Names are those of the chart at the tag (release and chart name kevgate, so the fullname is
# kevgate; PVC kevgate-data; Secret kevgate-api-keys; client label kevgate-client=true) and of the workflows in .github/workflows.
# ---------------------------------------------------------------------------------------------------------------------
ARCH_DESCS = [
    ("kevgate request path",
     "A client pod labelled kevgate-client=true reaches the Service on port 8000 only through the NetworkPolicy. The pod runs as UID 10001 with a read-only "
     "root filesystem and keeps its SQLite database on a volume mounted at /data."),
    ("kevgate delivery pipeline",
     "The ci, security, deploy-kind and terraform workflows run on pull requests and pushes to main. The release workflow runs on a version tag."),
]

# (kind, title, subtitle). kind: lane (a heading), box, hi (emphasised), arrow (draw a connector after this item)
ARCH = [
    ("lane", "Request path, namespace kevgate", "Pod Security restricted enforced"),
    ("box", "Client pod", "label kevgate-client=true", True),
    ("hi", "NetworkPolicy kevgate", "ingress: labelled pods, TCP 8000; egress: DNS only", True),
    ("box", "Service kevgate", "ClusterIP, port 8000", True),
    ("hi", "Pod kevgate", "UID 10001, read-only root, no capabilities, no service-account token", True),
    ("box", "Volume kevgate-data", "/data: SQLite; keys from a read-only Secret", False),
    ("lane", "Pipeline, .github/workflows", "pull requests and pushes to main, then tags"),
    ("box", "ci", "ruff, mypy, pytest (Python 3.11, 3.12)", False),
    ("box", "security", "Semgrep, Bandit, pip-audit, gitleaks, checkov, Trivy", False),
    ("box", "deploy-kind", "kind and Calico: smoke, NetworkPolicy, Pod Security, ZAP", False),
    ("box", "terraform", "infra/ changes: validate, OIDC test, LocalStack", False),
    ("hi", "release, on a version tag", "scan, push to GHCR, sign, SBOM, provenance, verify", False),
]


def lane_svg(items: list[tuple], n: int, first_letter: int) -> tuple[str, list[tuple[str, str]], int]:
    vb_w, x0, bw, gap = 320, 26, 290, 16
    title, desc = ARCH_DESCS[n]
    y = 4
    parts: list[str] = []
    alt: list[tuple[str, str]] = []
    letter_i = first_letter
    for i, item in enumerate(items):
        kind = item[0]
        if kind == "lane":
            tl, sl = C.wrap(item[1], 36), C.wrap(item[2], 40)
            for ln in tl:
                parts.append(f'<text x="{x0 - 14}" y="{y + 14}" font-weight="600" font-size="14" text-decoration="underline">{C.esc(ln)}</text>')
                y += 18
            y += 2
            for ln in sl:
                parts.append(f'<text class="sub" x="{x0 - 14}" y="{y + 12}" font-size="12">{C.esc(ln)}</text>')
                y += 15
            y += 10
            alt.append(("lane", f"<p><strong>{C.esc(item[1])}.</strong> {C.esc(item[2])}.</p>"))
            continue
        _, a, b, arrow = item
        tl, sl = C.wrap(a, 30), C.wrap(b, 33)
        h = 14 + 19 * len(tl) + 17 * len(sl) + 10
        cls = ' class="hi"' if kind == "hi" else ""
        parts.append(f'<rect{cls} x="{x0}" y="{y}" width="{bw}" height="{h}"/>')
        ty = y + 22
        for ln in tl:
            parts.append(f'<text x="{x0 + 12}" y="{ty}" font-weight="600" font-size="14">{C.esc(ln)}</text>')
            ty += 19
        for ln in sl:
            parts.append(f'<text class="sub" x="{x0 + 12}" y="{ty - 1}" font-size="13">{C.esc(ln)}</text>')
            ty += 17
        parts.append(f'<circle class="letter" cx="{x0 - 14}" cy="{y + 12}" r="9"/><text class="lt" x="{x0 - 14}" y="{y + 16}">{chr(65 + letter_i)}</text>')
        letter_i += 1
        alt.append(("item", f"<li><strong>{C.esc(a)}.</strong> {C.esc(b)}.</li>"))
        nxt = items[i + 1] if i + 1 < len(items) else None
        if arrow and nxt:
            ax = x0 + bw // 2
            y1, y2 = y + h, y + h + gap
            parts.append(f'<path class="arrow" d="M{ax} {y1} V{y2 - 1}"/><path class="head" d="M{ax - 5} {y2 - 8} L{ax} {y2 - 1} L{ax + 5} {y2 - 8}"/>')
            y += h + gap
        else:
            y += h + (10 if nxt else 0)
    svg = (f'<svg viewBox="0 0 {vb_w} {y + 4}" role="img" aria-labelledby="kgarch{n}-t kgarch{n}-d">'
           f'<title id="kgarch{n}-t">{esc(title)}</title><desc id="kgarch{n}-d">{esc(desc)}</desc>{"".join(parts)}</svg>')
    return svg, alt, letter_i


def arch() -> str:
    lane_starts = [i for i, it in enumerate(ARCH) if it[0] == "lane"]
    lanes = [ARCH[a:b] for a, b in zip(lane_starts, lane_starts[1:] + [len(ARCH)])]
    svgs, alt_html, letter = [], [], 0
    for n, items in enumerate(lanes):
        svg, alt, nxt = lane_svg(items, n, letter)
        svgs.append(svg)
        alt_html.append(f"<p><strong>{C.esc(items[0][1])}.</strong> {C.esc(items[0][2])}.</p>"
                        f'<ol class="alt-list" type="A" start="{letter + 1}">{"".join(h for k, h in alt if k == "item")}</ol>')
        letter = nxt
    label = '<span class="plate-label">Figure {{n}}</span>'
    cap = ("How the chart and the workflows at the tag fit together. Letters A to E follow a request; F to J are the workflows. "
           "The release workflow's attestations and the kind job's NetworkPolicy and Pod Security checks are among the evidence cited in Figure 1.")
    return (f'<figure class="plate diagram kg-arch">{label}<div class="kg-lanes">{"".join(svgs)}</div><figcaption>{esc(cap)}</figcaption></figure>'
            f'<details class="alt"><summary>Describe this diagram</summary>{"".join(alt_html)}</details>')
