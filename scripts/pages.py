"""Page bodies: home, projects index, project template. Data comes from content/data/*.json; prose from content/*.html."""
from __future__ import annotations

import re
from html import escape as esc
from pathlib import Path

import bench_fuzzdiff_static as BF
import bench_kevgate_static as BK
import bench_static as B
import bench_vulnlab_static as BV
import components as C

ROOT = Path(__file__).resolve().parent.parent
GH = "https://github.com/samiali38183"
FOLD_ROWS = 5  # tables with at least this many body rows, and code blocks with FOLD_LINES lines, are folded on project pages
FOLD_LINES = 12


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
                    "fuzzdiff": BF.parser_static, "fuzzdiff-cap": BF.parser_caption, "fuzzdiff-mutants": BF.mutants_panel, "fuzzdiff-sweep": BF.sweep_table,
                    "kev-risk": B.kev_risk_static, "kev-risk-cap": B.kev_risk_caption,
                    "kevgate-admit": B.admit_static, "kevgate-admit-cap": B.admit_caption,
                    "vulnlab": BV.vulnlab_static, "vulnlab-cap": BV.vulnlab_caption,
                    "kevgate": BK.kevgate_static, "kevgate-cap": BK.kevgate_caption, "kevgate-what": BK.kevgate_what}[arg]()
        if kind == "kgarch":
            return BK.arch()
        if kind == "admitpath":
            return B.admit_path()
        if kind == "snapshot":
            return {"figure": B.kev_snapshot_plate}[arg]()
        if kind == "copy":
            return {"about": lambda: "".join(f"<p>{esc(x)}</p>" for x in ABOUT), "email": copy_email,
                    "experience": lambda: "".join(f"<li>{esc(b)}</li>" for b in EXPERIENCE)}[arg]()
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
# Home and projects index
# ---------------------------------------------------------------------------------------------
def ver_of(p: dict) -> str:
    return p["version"] if p["version"].startswith("v") else "main"


def tier(d: dict, name: str) -> list[dict]:
    return [d["projects"][s] for s in d["order"] if d["projects"][s]["tier"] == name]


def hero_fig(p: dict, cls: str, eager: bool = False, link: bool = True, key: str = "hero") -> str:
    """The project's hero image on a neutral card (the PNGs have a white background). Width and height reserve the space."""
    h = p[key]
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    img = (f'<img src="{h["src"]}" width="{h["w"]}" height="{h["h"]}" alt="{esc(h["alt"], quote=True)}" {load} decoding="async">')
    if link:
        img = f'<a class="hero-zoom" href="{h["src"]}" aria-label="Open the {esc(p["name"], quote=True)} {esc(h.get("label", "result"), quote=True)} image at full size">{img}</a>'
    return f'<figure class="hero-fig {cls}"><div class="hero-card">{img}</div><figcaption>{esc(h["caption"])}</figcaption></figure>'


def second_hero(p: dict) -> str:
    """An optional second image below the reading band, for pages whose lead image is not the engineering evidence."""
    return hero_fig(p, "hero-second", key="hero2") if "hero2" in p else ""


def reading_chips(ctx: dict, rd: dict) -> str:
    """Verdict stamp and run chips. A recording run that is red by design gets its reason in plain words and a green main-branch run beside it."""
    chips = [C.chip(rd["run"], ctx["runs"], rd.get("run_label"))]
    if rd.get("run_ok"):
        chips.append(C.chip(rd["run_ok"], ctx["runs"], rd.get("run_ok_label")))
    note = f'<p class="chip-note">{esc(rd["run_note"])}</p>' if rd.get("run_note") else ""
    return f'<p class="chips">{C.stamp(*rd["stamp"])} {" ".join(chips)}</p>{note}'


# ---------------------------------------------------------------------------------------------
# Home, work archive and shared copy
# ---------------------------------------------------------------------------------------------
EMAIL = "samiali38183@gmail.com"
LINKEDIN = "https://www.linkedin.com/in/sami-ali-1a4b89345"
HEADLINE = "Security engineering student building application-security and detection tools, with measured results."
INTRO = ("I'm a cybersecurity student at George Mason University (B.S. IT, May 2028) who builds application-security and detection tools, "
         "and tests where they fail. In summer 2026 I worked on the DHS/CBP Vulnerability Assessment Team. "
         "I'm looking for a Summer 2027 security engineering internship.")
ABOUT = [
    "I build detection and application-security tooling because a rule or a scanner that has never been run against real input only looks like coverage. "
    "I would rather find the miss myself, write it down and fix it than learn about it during an incident, so each project here carries a record of what it got wrong.",
    "I earned an A.S. in Information Technology at Northern Virginia Community College in May 2026 and am working toward a B.S. in Information Technology with a cybersecurity minor at George Mason University. "
    "I hold Security+ and the AWS Cloud Practitioner certification, and I am studying for OSCP and the AWS Certified Security - Specialty."]
CALL_KETTLE = {
    "name": "call-kettle", "kind": "AI agent security, Python", "url": "/projects/call-kettle/", "repo": GH + "/call-kettle",
    "blurb": "Phone receptionist backend (FastAPI, Twilio, Claude tool use) where the model only proposes actions and server code authorizes each one. "
             "A scripted attacker model runs 42 attacks and 6 normal requests against the real gate; all pass.",
    "label": "Scripted model, synthetic data",
    "hero": {"src": "/assets/img/call-kettle/hero-security-eval.png", "w": 1800, "h": 1120,
             "alt": "Summary of the evaluation: one case in which the caller says to ignore instructions and cancel another customer's booking, the scripted model asks to cancel it and the server check refuses with policy_disabled. 48 of 48 cases pass."},
}
EXPERIENCE = [
    "Matched Nessus/Tenable scan results against CISA's Known Exploited Vulnerabilities (KEV) catalog to find high-risk systems and aged findings.",
    "Designed a risk-based prioritization method weighing KEV status, asset criticality, exposure, EPSS (exploit likelihood) and CVSS (severity), because severity alone does not show which flaws attackers are exploiting; benchmarked remediation against CISA directive BOD 26-04 timelines.",
    "Built a multi-page Power BI dashboard and an executive briefing on actively exploited vulnerabilities for technical and leadership audiences.",
    "Wrote remediation recommendations aligned with NIST CSF.",
]


def copy_email(cls: str = "") -> str:
    """The visible address plus a Copy button. The button is hidden until site.js runs, so without JavaScript only the text and the mailto link remain."""
    return (f'<span class="email-copy {cls}"><a class="email" href="mailto:{EMAIL}">{EMAIL}</a> '
            f'<button type="button" class="copy-email" data-copy-email="{EMAIL}" hidden>Copy</button>'
            '<span class="copy-status" role="status" aria-live="polite"></span></span>')


def figure(p: dict) -> str:
    """Hero image on a white card. No caption: the blurb already says what kind of data it is."""
    h = p["hero"]
    img = (f'<img src="{h["src"]}" width="{h["w"]}" height="{h["h"]}" alt="{esc(h["alt"], quote=True)}" loading="lazy" decoding="async">')
    return (f'<figure class="shot"><a class="hero-zoom" href="{p["url"]}" tabindex="-1" aria-hidden="true">'
            f'<div class="hero-card">{img}</div></a></figure>')


def proj_links(p: dict) -> str:
    links = [("Write-up", f'/projects/{p["slug"]}/'), ("Source", GH + "/" + p["slug"])]
    for t, u in p["links"]:
        if t.startswith(("Live coverage report", "Sample HTML report")):
            links.append(("Live report" if t.startswith("Live") else "Sample report", u))
    return " ".join(f'<a href="{u}">{t}</a>' for t, u in links)


def home(ctx: dict) -> str:
    d = ctx["projects"]
    feats = []
    ck = CALL_KETTLE
    items = [(slug, {**d["projects"][slug], "url": f"/projects/{slug}/"}) for slug in d["home_order"]]
    items.append(("call-kettle", {**ck, "version": ""}))
    for i, (slug, p) in enumerate(items, 1):
        ver = f' <span class="ver">{esc(ver_of(p))}</span>' if p["version"] else ""
        links = proj_links(p) if slug != "call-kettle" else f'<a href="{ck["url"]}">Write-up</a> <a href="{ck["repo"]}">Source</a>'
        feats.append(
            f'<li class="feat"><div class="feat-text">'
            f'<p class="meta"><span class="no">{i:02d}</span> {esc(p["kind"])}{ver}</p>'
            f'<h3><a href="/projects/{slug}/">{esc(p["name"])}</a></h3>'
            f'<p class="blurb">{esc(p["blurb"])}</p>'
            f'<p class="links">{links}</p></div>{figure(p)}</li>')
    research = []
    for slug in ("fuzzdiff", "kev-risk-prioritization"):
        p = d["projects"][slug]
        research.append(f'<li><a href="/projects/{slug}/">{esc(p["name"])}</a> <span class="ver">{esc(ver_of(p))}</span><br>{esc(p["lede"])}</li>')
    bullets = "".join(f"<li>{esc(b)}</li>" for b in EXPERIENCE)
    return f"""<section class="intro" aria-labelledby="top">
<h1 id="top">Sami Ali</h1>
<p class="headline">{esc(HEADLINE)}</p>
<ul class="facts-strip">
<li>George Mason University, B.S. Information Technology, expected May 2028</li>
<li>DHS/CBP Vulnerability Assessment Team intern, summer 2026</li>
</ul>
<ul class="actions" aria-label="Resume and links">
<li><a class="btn" href="/resume.pdf">Resume (PDF)</a></li>
<li><a class="btn alt" href="https://github.com/samiali38183">GitHub</a></li>
<li><a class="btn alt" href="{LINKEDIN}">LinkedIn</a></li>
</ul>
<p class="email-line">{copy_email()}</p>
<p class="intro-text">{esc(INTRO)}</p>
</section>

<section class="section" aria-labelledby="work">
<h2 id="work">Selected work</h2>
<ol class="feats">{"".join(feats)}</ol>
<p class="more"><a href="/projects/">Work archive</a>: {len(d["order"]) - len(d["home_order"])} more projects.</p>
</section>

<section class="section" aria-labelledby="exp">
<h2 id="exp">Experience</h2>
<div class="entry">
<p class="entry-h"><strong>Vulnerability Assessment Team analyst intern</strong>, U.S. Department of Homeland Security (CBP), HS-POWER program. Ashburn, VA. Summer 2026.</p>
<ul>{bullets}</ul>
<p class="note-line">Work product is not published; the public projects use synthetic or open data. <a href="/experience/">Education and details</a></p>
</div>
</section>

<section class="section" aria-labelledby="research">
<h2 id="research">Additional research</h2>
<ul class="plain-list">{"".join(research)}</ul>
</section>

<section class="section" aria-labelledby="edu">
<h2 id="edu">Education and certifications</h2>
<dl class="facts">
<dt>George Mason University</dt><dd>B.S. Information Technology, Cybersecurity Minor. Expected May 2028.</dd>
<dt>Northern Virginia Community College</dt><dd>A.S. Information Technology, May 2026.</dd>
<dt>Certifications</dt><dd>CompTIA Security+ (SY0-701), AWS Certified Cloud Practitioner. Studying for OSCP.</dd>
</dl>
</section>

<section class="section" aria-labelledby="contact">
<h2 id="contact">Contact</h2>
<p class="contact-line">{copy_email("big")}</p>
<p><a href="https://github.com/samiali38183">github.com/samiali38183</a> &middot; <a href="{LINKEDIN}">LinkedIn</a> &middot; <a href="/resume.pdf">Resume (PDF)</a></p>
</section>"""


def archive_row(name: str, url: str, kind: str, ver: str, blurb: str, label: str, links: str) -> str:
    ver_html = f' <span class="ver">{esc(ver)}</span>' if ver else ""
    return (f'<li class="arow"><div class="a-head"><h2><a href="{url}">{esc(name)}</a></h2>'
            f'<p class="meta">{esc(kind)}{ver_html}</p></div>'
            f'<div class="a-body"><p class="blurb">{esc(blurb)}</p><p class="meta"><span class="tag">{esc(label)}</span></p>'
            f'<p class="links">{links}</p></div></li>')


def projects_index(ctx: dict) -> str:
    d = ctx["projects"]
    rows = []
    for slug in d["order"]:
        p = d["projects"][slug]
        if slug in d["home_order"]:
            continue
        rows.append(archive_row(p["name"], f"/projects/{slug}/", p["kind"], ver_of(p), p["blurb"], p["label"], proj_links(p)))
    feat = ", ".join([f'<a href="/projects/{s}/">{esc(d["projects"][s]["name"])}</a>' for s in d["home_order"]]
                     + [f'<a href="{CALL_KETTLE["url"]}">call-kettle</a>'])
    return f"""<h1>Work archive</h1>
<p class="dek">Projects that are not featured on the <a href="/">home page</a>. Featured: {feat}.</p>
<ol class="archive">{"".join(rows)}</ol>"""


# ---------------------------------------------------------------------------------------------
# Project page (6.3)
# ---------------------------------------------------------------------------------------------
def fold(summary: str, body: str, cls: str = "") -> str:
    """A closed native details element. Everything inside stays in the page for crawlers and for readers without JavaScript."""
    c = "fold" + (f" {cls}" if cls else "")
    return f'<details class="{c}"><summary>{summary}</summary>{body}</details>'


_TABLE_BOX = re.compile(r'<div class="scroll wide">\s*<table\b[^>]*>(?:(?!</table>).)*?</table>\s*</div>', re.S)
_PRE = re.compile(r'<pre\b[^>]*>.*?</pre>', re.S)


def fold_long(html: str) -> str:
    """Wrap long evidence tables and long code blocks in a details element (closed). Short ones stay in the flow."""
    def tbl(m: re.Match) -> str:
        box = m.group(0)
        rows = len(re.findall(r"<tr\b", re.search(r"<tbody>.*</tbody>", box, re.S).group(0))) if "<tbody>" in box else 0
        if rows < FOLD_ROWS:
            return box
        cap = re.search(r"<caption>(.*?)</caption>", box, re.S)
        name = re.sub(r"<[^>]+>", "", cap.group(1)).strip() if cap else "Table"
        return fold(f"Table, {rows} rows: {name}", box, "fold-tbl")

    def pre(m: re.Match) -> str:
        block = m.group(0)
        lines = block.count("\n") + 1
        if lines < FOLD_LINES:
            return block
        lab = re.search(r'data-label="([^"]*)"', block)
        name = lab.group(1) if lab else "Code"
        return fold(f"Output, {lines} lines: {name}", block, "fold-tbl")

    # Do not fold inside an element that is already a details element.
    parts = re.split(r"(<details\b.*?</details>)", html, flags=re.S)
    out = []
    for part in parts:
        if part.startswith("<details"):
            out.append(part)
        else:
            out.append(_PRE.sub(pre, _TABLE_BOX.sub(tbl, part)))
    return "".join(out)


def record_head(p: dict, dek: str) -> str:
    r = p["record"]
    repro = "\n".join(r["reproduce"])
    inner = f"""<section class="record-head" aria-label="Verification record">
<dl>
<div><dt>Version tested</dt><dd>{esc(r["instrument"])}</dd></div>
<div><dt>Checked against</dt><dd>{esc(r["reference"])}</dd></div>
<div><dt>Run on</dt><dd>{esc(r["measured"])}</dd></div>
<div><dt>Run by</dt><dd>Sami Ali. Not independently audited.</dd></div>
<div class="full"><dt>Reproduce</dt><dd><pre data-copy data-label="{esc(r["reproduce_label"])}"><code>{esc(repro)}</code></pre></dd></div>
</dl>
</section>"""
    return fold("How the check was run: version, reference, date, how to reproduce", inner, "fold-rec")


def reading_band(ctx: dict, p: dict) -> str:
    rd = p["reading"]
    main = p["strip_sets"]["main"]
    den = f'<span class="den" aria-hidden="true">{esc(rd["den"])}</span>' if rd["den"] else ""
    aria = f'Result: {rd["num"]}{rd["den"]} {rd["unit"]}'
    return f"""<section class="reading-band" aria-label="The result">
<div class="hero-read">
<p class="reading sm k-{rd["stamp"][0]}" role="img" aria-label="{esc(aria, quote=True)}"><span aria-hidden="true">{esc(rd["num"])}</span>{den}</p>
<div>
<p class="why">{esc(rd["caption"])}</p>
{reading_chips(ctx, rd)}
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
    body = f"""<p class="prose muted">Run states were captured when the site was built.</p>
<dl class="trace">{"".join(items)}</dl>
{extra}"""
    return f"""<section class="section fold-sec" id="trace" aria-labelledby="trace-h">
<details class="fold fold-main"><summary><span class="label sec-label">Evidence</span><h2 id="trace-h">Where each number comes from</h2><span class="fold-hint">{len(items)} links</span></summary>
{body}
</details>
</section>"""


def sheets(ctx: dict, p: dict) -> str:
    d = ctx["projects"]
    order = d["order"]
    i = order.index(p["slug"])
    prev = nxt = ""
    if i > 0:
        q = d["projects"][order[i - 1]]
        prev = f'<a class="prev" href="/projects/{q["slug"]}/"><span class="label">Previous</span><span class="n">{esc(q["name"])}</span></a>'
    if i < len(order) - 1:
        q = d["projects"][order[i + 1]]
        nxt = f'<a class="next" href="/projects/{q["slug"]}/"><span class="label">Next</span><span class="n">{esc(q["name"])}</span></a>'
    return f'<nav class="sheets" aria-label="Other projects">{prev}{nxt}</nav>'


def project_page(ctx: dict, slug: str) -> str:
    p = ctx["projects"]["projects"][slug]
    f = fragments(p["content"])
    ex = lambda s: expand(ctx, s, p)  # noqa: E731
    labels = p["labels"]
    links = "".join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in p["links"])
    note = f'<p class="small muted">{esc(p["note"])}</p>' if p.get("note") else ""
    bench = ""
    if "bench" in f:
        after = ex(f["bench-after"]) + chr(10) if "bench-after" in f else ""
        bench = f"""<section class="bench" data-bench="{p.get("bench", slug)}" aria-label="Recorded readings">
<figure class="plate">
<span class="plate-label">Figure {{{{n}}}}</span>
<div class="bench-static">
{ex(f["bench"])}
</div>
<div class="bench-live" data-bench-mount hidden></div>
{after}<figcaption>{ex(f["bench-cap"])}</figcaption>
</figure>
</section>"""
    tr = p["try"]
    has_bench = "bench" in f
    if has_bench:
        bench = bench.replace('<section class="bench"', f'<section class="bench" id="try"', 1)
        bench = (f'<div class="try-head"><h2>{esc(tr["kind"])}</h2><p>{esc(tr["text"])}</p></div>\n' + bench)
    overview = "".join(f"<p>{esc(x)}</p>" for x in p["overview"])
    jump = []
    if has_bench:
        jump.append(f'<li><a href="#try">{esc(tr["kind"])}</a></li>')
    jump.append('<li><a href="#limits">Limits</a></li>')
    return f"""<div class="sheet">
<header class="title has-hero">
<p class="crumb"><a href="/projects/">Work</a> <span aria-hidden="true">/</span> {esc(p["kind"])} <span class="ver">{esc(ver_of(p))}</span></p>
<h1>{esc(p["name"])}</h1>
<div class="overview prose">{overview}</div>
<ul class="linkrow">{"".join(jump)}{links}</ul>
{note}
{hero_fig(p, "page-hero", eager=True)}
</header>
{reading_band(ctx, p)}
{second_hero(p)}
{bench}
{record_head(p, ex(f["dek"]))}
<article class="record">
<section class="section" id="as-found" aria-labelledby="found-h">
<h2 id="found-h"><span class="label sec-label">{esc(labels["found"])}</span>{esc(p["found_title"])}</h2>
{fold_long(ex(f["as-found"]))}
</section>
<section class="section" id="as-left" aria-labelledby="left-h">
<h2 id="left-h"><span class="label sec-label">{esc(labels["left"])}</span>{esc(p["left_title"])}</h2>
{fold_long(ex(f["as-left"]))}
</section>
<section class="section fold-sec" id="method" aria-labelledby="method-h">
<details class="fold fold-main"><summary><span class="label sec-label">Technical details</span><h2 id="method-h">How it works</h2><span class="fold-hint">design, implementation points and diagram</span></summary>
<div class="fold-body">
{ex(f["method"])}
</div>
</details>
</section>
</article>
<section class="limits section" id="limits" aria-labelledby="limits-h">
<h2 id="limits-h">Limits</h2>
{ex(f["limits"])}
</section>
{trace(ctx, p, ex(f.get("trace", "")))}
{sheets(ctx, p)}
</div>"""
