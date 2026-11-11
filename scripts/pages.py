"""Page bodies: home, projects index, project template. Data comes from content/data/*.json; prose from content/*.html."""
from __future__ import annotations

import re
from html import escape as esc
from pathlib import Path

import bench_static as B
import components as C

ROOT = Path(__file__).resolve().parent.parent
GH = "https://github.com/samiali38183"


# ---------------------------------------------------------------------------------------------
# Content fragments: files with <!--@name--> markers, split into named chunks.
# ---------------------------------------------------------------------------------------------
def fragments(fname: str) -> dict[str, str]:
    text = (ROOT / "content" / fname).read_text(encoding="utf-8")
    parts = re.split(r"<!--@([a-z-]+)-->", text)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_chip(ctx: dict, rid: str) -> str:
    return C.chip(rid, ctx["runs"])


def expand(ctx: dict, text: str, p: dict | None = None) -> str:
    """Replace placeholders: {{run:ID}} {{stamp:kind:text}} {{diagram:key}} {{strips:name}} {{key:name}} {{kb:file}}."""
    def sub(m: re.Match) -> str:
        kind, _, arg = m.group(1).partition(":")
        if kind == "run":
            return run_chip(ctx, arg)
        if kind == "stamp":
            k, _, t = arg.partition(":")
            return C.stamp(k, t)
        if kind == "diagram":
            return C.diagram(arg)
        if kind == "strips":
            return C.strip_rows(p["strip_sets"][arg])
        if kind == "key":
            return C.key(p["strip_sets"][arg])
        if kind == "bench":
            return {"sinkline": B.sinkline_static, "sinkline-cap": B.sinkline_caption,
                    "kev-risk": B.kev_risk_static, "kev-risk-cap": B.kev_risk_caption,
                    "kevgate-admit": B.admit_static, "kevgate-admit-cap": B.admit_caption}[arg]()
        if kind == "admitpath":
            return B.admit_path()
        if kind == "snapshot":
            return {"figure": B.kev_snapshot_plate}[arg]()
        if kind == "kb":
            return f"{round((ROOT / arg).stat().st_size / 1000)} KB"
        if kind == "benchtable":
            return bench_table(arg)
        if kind == "benchevents":
            return bench_events(arg)
        if kind == "parity":
            return str(_bench_data(arg)[0]["meta"]["parity_cases"])
        raise KeyError(m.group(0))
    return re.sub(r"\{\{([a-z]+:[^{}]+)\}\}", sub, text)


# ---------------------------------------------------------------------------------------------
# Bench static state (tripline): generated from the same data the live bench and its parity test use
# ---------------------------------------------------------------------------------------------
def _bench_data(name: str) -> tuple[dict, dict]:
    import json
    data = json.loads((ROOT / f"assets/data/bench-{name}.json").read_text(encoding="utf-8"))
    parity = json.loads((ROOT / f"assets/data/{name}-bench-parity.json").read_text(encoding="utf-8"))
    return data, parity


def _verdict(on: int) -> str:
    return C.stamp("plain" if on else "off", "Flagged" if on else "Not flagged")


def bench_table(name: str) -> str:
    """Preset command lines with both rules' verdicts and reasons, from the generator's ground truth."""
    data, parity = _bench_data(name)
    cases = [c for c in parity["cases"] if c["g"] == "preset"]
    assert len(cases) == len(data["presets"])
    rows = []
    for pre, c in zip(data["presets"], cases):
        assert (pre["i"], pre["c"]) == (c["i"], c["c"])
        rows.append(
            f'<tr><th scope="row"><span class="label">{esc(pre["l"])}</span><br><code>{esc(c["c"])}</code>'
            f'<br><span class="label">Image {esc(c["i"])}</span></th>'
            f'<td>{_verdict(c["s"][2])}<p>{esc(c["w"][0])}</p></td>'
            f'<td>{_verdict(c["r"][4])}<p>{esc(c["w"][1])}</p></td></tr>')
    m = data["meta"]
    return (f'<div class="scroll wide"><table class="tbl bt"><caption>Recorded verdicts: what each rule decides on {len(rows)} command lines '
            f'(evaluated by tripline {esc(m["tripline"])}, commit {esc(m["commit"])})</caption>'
            '<thead><tr><th scope="col">Command line</th><th scope="col">Stock rule c21c4eaa</th>'
            '<th scope="col">Replacement rule</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def bench_events(name: str) -> str:
    """The 36 recorded events with both verdicts, inside a details element."""
    data, _ = _bench_data(name)
    rows = []
    for n, e in enumerate(data["events"], 1):
        exp = " (expected)" if n - 1 in data["expected"] else ""
        rows.append(
            f'<tr><th scope="row" class="num">{n}{exp}</th><td><code>{esc(e["i"])}</code></td><td><code>{esc(e["c"])}</code></td>'
            f'<td>{"<b>Flagged</b>" if e["s"] else "Not flagged"}</td><td>{"<b>Flagged</b>" if e["r"] else "Not flagged"}</td></tr>')
    return ('<details class="alt"><summary>All 36 recorded events and what each rule decided</summary>'
            '<div class="scroll wide"><table class="tbl bt"><caption>Applicable events from the recorded run, in order; '
            'command lines trimmed to 110 characters</caption>'
            '<thead><tr><th scope="col">Event</th><th scope="col">Image</th><th scope="col">Command line</th>'
            '<th scope="col">Stock rule</th><th scope="col">Replacement rule</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div></details>")


# ---------------------------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------------------------
def home(ctx: dict) -> str:
    d = ctx["projects"]
    t = d["projects"]["tripline"]
    main = t["strip_sets"]["main"]
    rows = []
    for slug in d["order"]:
        p = d["projects"][slug]
        sset = p["strip_sets"]["main"]
        minis = C.strip_rows(sset, mini=True)
        rows.append(
            f'<tr><th scope="row" class="name"><a href="/projects/{slug}/">{esc(p["name"])}</a><span class="ver">{esc(p["version"])}</span></th>'
            f'<td>{esc(p["home"]["against"])}</td><td>{minis}</td>'
            f'<td class="rd"><b>{esc(p["home"]["reading"])}</b></td><td>{run_chip(ctx, p["home"]["run"])}</td></tr>')
    ledger = (
        '<table class="tbl wt ledger"><caption class="vh">Record of checks: six tools, what each was checked against and the reading</caption>'
        '<thead><tr><th scope="col">Instrument</th><th scope="col">Checked against</th><th scope="col">As found, then as left</th>'
        '<th scope="col">Reading</th><th scope="col">Evidence</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    ff = []
    for item in d["failed_first"]:
        p = d["projects"][item["project"]]
        ff.append(
            f'<tr><th scope="row" class="name"><a href="/projects/{item["project"]}/#{item["anchor"]}">{esc(p["name"])}</a></th>'
            f'<td>{esc(item["text"])}</td><td>{C.stamp(*item["state"])}</td>'
            f'<td><a href="{item["src"][1]}">{esc(item["src"][0])}</a></td></tr>')
    failed = (
        '<table class="tbl wt"><caption class="vh">What failed first, with the source of each item</caption>'
        '<thead><tr><th scope="col">Instrument</th><th scope="col">What the check found</th><th scope="col">State</th><th scope="col">Source</th></tr></thead>'
        "<tbody>" + "".join(ff) + "</tbody></table>")
    rd = t["reading"]
    return f"""<section class="hero" aria-labelledby="top">
<h1 id="top">Security tools, checked against what they claim.</h1>
<p class="dek">Detection engineering, application security and vulnerability management. George Mason University, class of 2028.</p>
<div class="hero-read">
<p class="reading" role="img" aria-label="Reading: 0 of 36 events matched"><span aria-hidden="true">0</span><span class="den" aria-hidden="true">/36</span></p>
<div>
<p class="why">SigmaHQ's stock Setuid and Setgid rule matched 0 of 36 events in telemetry recorded from Atomic Red Team's T1548.001 tests on a GitHub-hosted Linux runner. The replacement rule matches 2.</p>
<p class="chips">{C.stamp("fail", "As found: fail")} {run_chip(ctx, rd["run"])}</p>
</div>
</div>
<div class="hero-strips">
{C.key(main)}
{C.strip_rows(main)}
</div>
<p><a class="arrow-link" href="/projects/tripline/#as-found">Read the record</a></p>
</section>

<section class="section" aria-labelledby="rec">
<div class="sec-head"><h2 id="rec">Record of checks</h2></div>
<p class="ledger-note">Each tool was checked against a reference and the reading is on its sheet. The strips show the same units as the sheet, reduced to at most 24 ticks: top row as found, bottom row as left. Where a project has only one row, it is the reading.</p>
{ledger}
</section>

<section class="section" aria-labelledby="ff">
<div class="sec-head"><h2 id="ff">What failed first</h2></div>
<p class="ledger-note">Each item is copied from the repository text it links to.</p>
{failed}
</section>

<section class="section prose" aria-labelledby="exp">
<h2 id="exp">Experience</h2>
<p><strong>U.S. Department of Homeland Security (CBP), HS-POWER Program</strong>, Vulnerability Assessment Team analyst intern, May to August 2026. Matched Nessus/Tenable scan results against the CISA KEV catalog, designed a risk-based prioritization method, and built a Power BI dashboard and executive briefing. <a href="/experience/">Details</a></p>
</section>

<section class="section prose" aria-labelledby="certs">
<h2 id="certs">Education and certifications</h2>
<ul>
<li>B.S. Information Technology, Cybersecurity Minor, George Mason University, expected May 2028</li>
<li>CompTIA Security+ and AWS Certified Cloud Practitioner</li>
<li>In progress: OSCP and AWS Certified Security - Specialty</li>
</ul>
</section>"""


# ---------------------------------------------------------------------------------------------
# Projects index
# ---------------------------------------------------------------------------------------------
def projects_index(ctx: dict) -> str:
    d = ctx["projects"]
    cards, rows = [], []
    for slug in d["order"]:
        p = d["projects"][slug]
        sset = p["strip_sets"]["main"]
        cards.append(
            f'<li><p class="tag label">Sheet {p["sheet"]} of 6 &middot; {esc(p["kind"])}</p>'
            f'<h2><a href="/projects/{slug}/">{esc(p["name"])}</a></h2>'
            f'<p class="rd">{esc(p["home"]["reading"])}</p>'
            f'{C.strip_rows(sset, mini=True, vt="strip-" + slug)}'
            f'<p class="fact">{esc(p["fact"])}</p></li>')
        rows.append(
            f'<tr><th scope="row" class="name"><a href="/projects/{slug}/">{esc(p["name"])}</a></th>'
            f'<td>{esc(p["record"]["reference"][0].upper() + p["record"]["reference"][1:])}</td>'
            f'<td>{esc(p["home"]["found"])}</td><td>{esc(p["home"]["left"])}</td>'
            f'<td>{esc(p["home"]["tolerance"])}</td><td>{run_chip(ctx, p["home"]["run"])}</td>'
            f'<td class="num">{esc(p["version"] if p["version"].startswith("v") else "commit " + p["commit"])}</td></tr>')
    table = (
        '<table class="tbl wt"><caption class="vh">Full ledger: reference standard, reading as found and as left, limits, evidence and version for each project</caption>'
        '<thead><tr><th scope="col">Instrument</th><th scope="col">Reference standard</th><th scope="col">As found</th><th scope="col">As left</th>'
        '<th scope="col">Tolerance</th><th scope="col">Evidence</th><th scope="col" class="num">Version</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    return f"""<h1>Projects</h1>
<p class="dek">Each project is an instrument. This page lists what it was checked against and what the check found.</p>
<ul class="multi" aria-label="Six projects">
{"".join(cards)}
</ul>
<section aria-labelledby="ledger">
<h2 id="ledger">Full ledger</h2>
<p class="ledger-note">Where a project has no earlier failure on record, the columns read Reference and Reading instead, and the sheet says so. Small strips are reduced to at most 24 ticks; every sheet shows the real counts.</p>
{table}
</section>
<section class="section prose" aria-labelledby="other">
<h2 id="other">Other repositories</h2>
<p class="muted">Public, but not the work I would point to first.</p>
<ul>
<li><a href="https://github.com/samiali38183/call-kettle">call-kettle</a>: phone receptionist backend with booking rules enforced in code and per-tenant limits. A sanitized snapshot; no customers.</li>
<li><a href="https://github.com/samiali38183/agent-engineering-lab">agent-engineering-lab</a>: notes on test gates, load tests and review rules for a private codebase. Writing, not a tool.</li>
<li><a href="https://github.com/samiali38183/focuslog">focuslog</a>: a single-file Pomodoro timer and session log. An early project.</li>
</ul>
</section>"""


# ---------------------------------------------------------------------------------------------
# Project page (6.3)
# ---------------------------------------------------------------------------------------------
def record_head(p: dict) -> str:
    r = p["record"]
    repro = "\n".join(r["reproduce"])
    return f"""<section class="record-head" aria-label="Verification record">
<dl>
<div><dt>Instrument</dt><dd>{esc(r["instrument"])}</dd></div>
<div><dt>Reference standard</dt><dd>{esc(r["reference"])}</dd></div>
<div><dt>Measured on</dt><dd>{esc(r["measured"])}</dd></div>
<div><dt>Issued by</dt><dd>The author. Self-issued verification record, not accredited.</dd></div>
<div class="full"><dt>Reproduce</dt><dd><pre data-copy data-label="{esc(r["reproduce_label"])}"><code>{esc(repro)}</code></pre></dd></div>
</dl>
</section>"""


def reading_band(ctx: dict, p: dict) -> str:
    rd = p["reading"]
    main = p["strip_sets"]["main"]
    den = f'<span class="den" aria-hidden="true">{esc(rd["den"])}</span>' if rd["den"] else ""
    aria = f'Reading: {rd["num"]}{rd["den"]} {rd["unit"]}'
    return f"""<section class="reading-band" aria-label="The reading">
<div class="hero-read">
<p class="reading sm" role="img" aria-label="{esc(aria, quote=True)}"><span aria-hidden="true">{esc(rd["num"])}</span>{den}</p>
<div>
<p class="why">{esc(rd["caption"])}</p>
<p class="chips">{C.stamp(*rd["stamp"])} {run_chip(ctx, rd["run"])}</p>
</div>
</div>
{C.key(main)}
{C.strip_rows(main, vt="strip-" + p["slug"])}
</section>"""


def trace(ctx: dict, p: dict, extra: str) -> str:
    items = []
    for t in p["trace"]:
        if t[1] == "run":
            val = run_chip(ctx, t[2])
        else:
            val = f'<a href="{t[2]}">{esc(t[3])}</a>'
        items.append(f'<div><dt>{esc(t[0])}</dt><dd>{val}</dd></div>')
    return f"""<section class="section" id="trace" aria-labelledby="trace-h">
<h2 id="trace-h"><span class="label sec-label">Traceability</span>Where each number comes from</h2>
<p class="prose muted">Chips show the state of each GitHub Actions run as captured when this page was built. The page does not call GitHub at runtime.</p>
<dl class="trace">{"".join(items)}</dl>
{extra}
</section>"""


def sheets(ctx: dict, p: dict) -> str:
    d = ctx["projects"]
    order = d["order"]
    i = order.index(p["slug"])
    prev = nxt = ""
    if i > 0:
        q = d["projects"][order[i - 1]]
        prev = f'<a class="prev" href="/projects/{q["slug"]}/"><span class="label">Previous sheet, {q["sheet"]} of 6</span><span class="n">{esc(q["name"])}</span></a>'
    if i < len(order) - 1:
        q = d["projects"][order[i + 1]]
        nxt = f'<a class="next" href="/projects/{q["slug"]}/"><span class="label">Next sheet, {q["sheet"]} of 6</span><span class="n">{esc(q["name"])}</span></a>'
    return f'<nav class="sheets" aria-label="Sheets">{prev}{nxt}</nav>'


def project_page(ctx: dict, slug: str) -> str:
    p = ctx["projects"]["projects"][slug]
    f = fragments(p["content"])
    ex = lambda s: expand(ctx, s, p)  # noqa: E731
    labels = p["labels"]
    links = "".join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in p["links"])
    note = f'<p class="small muted">{esc(p["note"])}</p>' if p.get("note") else ""
    bench = ""
    if "bench" in f:
        bench = f"""<section class="bench" data-bench="{p.get("bench", slug)}" aria-label="Recorded readings">
<figure class="plate">
<span class="plate-label">Plate {{{{n}}}}</span>
<div class="bench-static">
{ex(f["bench"])}
</div>
<div class="bench-live" data-bench-mount hidden></div>
<figcaption>{ex(f["bench-cap"])}</figcaption>
</figure>
</section>"""
    return f"""<div class="sheet">
<header class="title">
<h1>{esc(p["name"])}</h1>
<p class="dek">{ex(f["dek"])}</p>
<ul class="linkrow">{links}</ul>
{note}
</header>
{record_head(p)}
{reading_band(ctx, p)}
{bench}
<article class="record">
<section class="section" id="as-found" aria-labelledby="found-h">
<h2 id="found-h"><span class="label sec-label">{esc(labels["found"])}</span>{esc(p["found_title"])}</h2>
{ex(f["as-found"])}
</section>
<section class="section" id="as-left" aria-labelledby="left-h">
<h2 id="left-h"><span class="label sec-label">{esc(labels["left"])}</span>{esc(p["left_title"])}</h2>
{ex(f["as-left"])}
</section>
<section class="section" id="method" aria-labelledby="method-h">
<h2 id="method-h"><span class="label sec-label">Method</span>How it works</h2>
{ex(f["method"])}
</section>
</article>
<section class="limits section" id="limits" aria-labelledby="limits-h">
<h2 id="limits-h"><span class="label sec-label">Tolerance and limits</span>What the numbers do not show</h2>
{ex(f["limits"])}
</section>
{trace(ctx, p, ex(f.get("trace", "")))}
{sheets(ctx, p)}
</div>"""
