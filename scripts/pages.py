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


def work_list(plist: list[dict], cls: str = "") -> str:
    """The project list: number, name, one plain sentence, the reading, and the as found / as left strips."""
    items = []
    for p in plist:
        items.append(
            f'<li><span class="no" aria-hidden="true">{p["sheet"]:02d}</span>'
            f'<div class="w-main"><h3><a href="/projects/{p["slug"]}/">{esc(p["name"])}</a> <span class="ver">{esc(ver_of(p))}</span></h3>'
            f'<p class="w-kind">{esc(p["kind"])}</p>'
            f'<p class="w-lede">{esc(p["lede"])}</p>'
            f'<p class="w-res"><span class="w-rl">Result</span> {esc(p["home"]["reading"])}</p></div>'
            f'<div class="w-viz">{C.strip_rows(p["strip_sets"]["main"], mini=True, vt="strip-" + p["slug"])}</div></li>')
    return f'<ol class="work {cls}">{"".join(items)}</ol>'


def reading_chips(ctx: dict, rd: dict) -> str:
    """Verdict stamp and run chips. A recording run that is red by design gets its reason in plain words and a green main-branch run beside it."""
    chips = [C.chip(rd["run"], ctx["runs"], rd.get("run_label"))]
    if rd.get("run_ok"):
        chips.append(C.chip(rd["run_ok"], ctx["runs"], rd.get("run_ok_label")))
    note = f'<p class="chip-note">{esc(rd["run_note"])}</p>' if rd.get("run_note") else ""
    return f'<p class="chips">{C.stamp(*rd["stamp"])} {" ".join(chips)}</p>{note}'


def home(ctx: dict) -> str:
    d = ctx["projects"]
    t = d["projects"]["tripline"]
    main = t["strip_sets"]["main"]
    n = len(d["order"])
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
        f'<table class="tbl wt ledger"><caption class="vh">All checks: {n} projects, what each was checked against and the result</caption>'
        '<thead><tr><th scope="col">Project</th><th scope="col">Checked against</th><th scope="col">Before, then after</th>'
        '<th scope="col">Result</th><th scope="col">Evidence</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    ff = []
    for item in d["failed_first"]:
        p = d["projects"][item["project"]]
        ff.append(
            f'<tr><th scope="row" class="name"><a href="/projects/{item["project"]}/#{item["anchor"]}">{esc(p["name"])}</a></th>'
            f'<td>{esc(item["text"])}</td><td>{C.stamp(*item["state"])}</td>'
            f'<td><a href="{item["src"][1]}">{esc(item["src"][0])}</a></td></tr>')
    head = ('<thead><tr><th scope="col">Project</th><th scope="col">What the check found</th><th scope="col">State</th><th scope="col">Source</th></tr></thead>')
    failed = ('<table class="tbl wt"><caption class="vh">Problems found, with the source of each item</caption>' + head +
              "<tbody>" + "".join(ff) + "</tbody></table>")
    rd = t["reading"]
    den = f'<span class="den" aria-hidden="true">{esc(rd["den"])}</span>'
    aria = f'Result: {rd["num"]}{rd["den"]} {rd["unit"]}'
    return f"""<section class="hero" aria-labelledby="top">
<h1 id="top">I build security tools, then check them against <span class="hl">something I did not write</span>.</h1>
<p class="dek">I'm Sami Ali, a student at George Mason University (class of 2028). I write detection rules, code analyzers and vulnerability-ranking tools. Each one is tested against recorded data, an outside benchmark or the original it copies.</p>
<p class="row cta"><a class="btn" href="#work">See the work</a> <a class="btn alt" href="/resume/">Resume</a> <a class="btn alt" href="mailto:samiali38183@gmail.com">Email me</a></p>
<dl class="at-a-glance" aria-label="At a glance">
<div><dt>Looking for</dt><dd>Summer 2027 security internships</dd></div>
<div><dt>School</dt><dd>George Mason University, class of 2028</dd></div>
<div><dt>Experience</dt><dd>DHS (CBP) vulnerability assessment intern, summer 2026</dd></div>
<div><dt>Certifications</dt><dd>Security+, AWS Cloud Practitioner</dd></div>
<div><dt>Work authorization</dt><dd>U.S. citizen</dd></div>
</dl>
<div class="hero-read">
<p class="reading k-{rd["stamp"][0]}" role="img" aria-label="{esc(aria, quote=True)}"><span aria-hidden="true">{esc(rd["num"])}</span>{den}</p>
<div>
<p class="kicker">The short version</p>
<p class="say">Security teams use detection rules like tripwires: when an attack happens, the rule should raise an alert. I replayed a real recording of one attack against a widely used public rule, and it raised no alert for either of the 2 attack steps. The rule I wrote alerts on both.</p>
<details class="fold tech"><summary>Technical detail</summary>
<p class="why">A public SigmaHQ rule is meant to notice a program being set to run with its owner's privileges (setuid and setgid, ATT&amp;CK T1548.001). {esc(rd["caption"])}</p>
{reading_chips(ctx, rd)}
</details>
</div>
</div>
<div class="hero-strips">
{C.key(main)}
{C.strip_rows(main)}
</div>
<p><a class="arrow-link" href="/projects/tripline/#as-found">Read the full results</a></p>
</section>

<section class="section" aria-labelledby="work">
<div class="sec-head"><h2 id="work">The work</h2><p class="sec-aside">Each project has a one-line summary, a result, and a page with the details. In each pair of strips, the top row is before the fix and the bottom row is after.</p></div>
{work_list(tier(d, "featured"))}
<h3 class="also-h" id="also">Smaller projects</h3>
{work_list(tier(d, "also"), "compact")}
<p><a class="arrow-link" href="/projects/">All {n} projects</a></p>
</section>

<section class="section prose" aria-labelledby="skills">
<h2 id="skills">What I work with</h2>
<ul class="tags">
<li>Detection engineering (Sigma, ATT&amp;CK)</li><li>Application security</li><li>Vulnerability management</li><li>Python</li><li>Go</li><li>Rust</li><li>Kubernetes</li><li>CI/CD and GitHub Actions</li><li>Terraform and Helm</li><li>Fuzzing</li><li>Power BI</li>
</ul>
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
</section>

<section class="section prose" aria-labelledby="terms">
<h2 id="terms">Terms used on this site</h2>
<details class="fold"><summary>Plain definitions, for anyone not working in security</summary>
<dl class="terms">
<div><dt>Detection rule</dt><dd>A rule that watches system activity and raises an alert when it matches a known attack pattern.</dd></div>
<div><dt>Sigma</dt><dd>A shared, open format for writing detection rules so they work across different security tools.</dd></div>
<div><dt>MITRE ATT&amp;CK</dt><dd>A public catalog of attacker techniques, each with an ID such as T1548.001.</dd></div>
<div><dt>CI (continuous integration)</dt><dd>Automatic checks that run every time code changes. A failed check blocks the change.</dd></div>
<div><dt>CISA KEV</dt><dd>The U.S. government's list of vulnerabilities that attackers are known to be exploiting right now.</dd></div>
<div><dt>CVSS and EPSS</dt><dd>Two scores for vulnerabilities: how severe one is (CVSS) and how likely it is to be exploited (EPSS).</dd></div>
<div><dt>Fuzzing</dt><dd>Feeding a program large amounts of odd input to see whether it breaks or behaves differently.</dd></div>
<div><dt>Kubernetes</dt><dd>Software that runs and manages containerized applications across many machines.</dd></div>
</dl>
</details>
</section>

<section class="section" aria-labelledby="ev">
<div class="sec-head"><h2 id="ev">The evidence</h2></div>
<p class="ledger-note">Every number above comes from these two tables and the CI runs they link to. Both tables are complete. They start closed to keep the page short.</p>
<details class="fold fold-main fold-ev"><summary><span class="label sec-label">All checks</span><span class="fold-t" id="rec">What each of the {n} projects was checked against</span><span class="fold-hint">The strips use the same units as each project page, cut down to at most 24 ticks. Top row is before, bottom row is after.</span></summary>
{ledger}
</details>
<details class="fold fold-main fold-ev"><summary><span class="label sec-label">Problems found</span><span class="fold-t" id="ff">{len(ff)} problems, each copied from the repository text it links to</span><span class="fold-hint">What was broken or missing before the fix.</span></summary>
{failed}
</details>
</section>"""


def projects_index(ctx: dict) -> str:
    d = ctx["projects"]
    return f"""<h1>Projects</h1>
<p class="dek">Seven projects. Each was checked against something other than my own opinion, and the result is on its row. The table with every reference and CI run is on the <a href="/#rec">home page</a>.</p>
<section aria-labelledby="featured">
<h2 id="featured">Featured</h2>
{work_list(tier(d, "featured"))}
</section>
<section class="section" aria-labelledby="also">
<h2 id="also">Also</h2>
{work_list(tier(d, "also"), "compact")}
</section>
<section class="section prose" aria-labelledby="other">
<h2 id="other">Other repositories</h2>
<p class="muted">Public, but not the work I would point to first.</p>
<ul>
<li><a href="https://github.com/samiali38183/call-kettle">call-kettle</a>: phone receptionist backend with booking rules enforced in code and per-tenant limits. A sanitized snapshot; no customers.</li>
<li><a href="https://github.com/samiali38183/focuslog">focuslog</a>: a single-file Pomodoro timer and session log. An early project.</li>
</ul>
</section>"""


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


def glance(p: dict) -> str:
    h = p["home"]
    return f"""<section class="glance" aria-label="At a glance">
<dl>
<div><dt>Checked against</dt><dd>{esc(h["against"])}</dd></div>
<div><dt>Before and after</dt><dd><span class="gl">Before</span> {esc(h["found"])}<br><span class="gl">After</span> {esc(h["left"])}</dd></div>
<div><dt>Limits</dt><dd>{esc(h["tolerance"])} <a href="#limits">Full limits</a></dd></div>
</dl>
</section>"""


def record_head(p: dict, dek: str) -> str:
    r = p["record"]
    repro = "\n".join(r["reproduce"])
    inner = f"""<p class="dek tech">{dek}</p>
<section class="record-head" aria-label="Verification record">
<dl>
<div><dt>Version tested</dt><dd>{esc(r["instrument"])}</dd></div>
<div><dt>Checked against</dt><dd>{esc(r["reference"])}</dd></div>
<div><dt>Run on</dt><dd>{esc(r["measured"])}</dd></div>
<div><dt>Run by</dt><dd>Sami Ali. Not independently audited.</dd></div>
<div class="full"><dt>Reproduce</dt><dd><pre data-copy data-label="{esc(r["reproduce_label"])}"><code>{esc(repro)}</code></pre></dd></div>
</dl>
</section>"""
    return fold("Technical description and how the check was run: version, reference, date, how to reproduce", inner, "fold-rec")


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
    body = f"""<p class="prose muted">Chips show the state of each GitHub Actions run as captured when this page was built. The page does not call GitHub at runtime.</p>
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
        prev = f'<a class="prev" href="/projects/{q["slug"]}/"><span class="label">Previous project, {q["sheet"]} of {len(order)}</span><span class="n">{esc(q["name"])}</span></a>'
    if i < len(order) - 1:
        q = d["projects"][order[i + 1]]
        nxt = f'<a class="next" href="/projects/{q["slug"]}/"><span class="label">Next project, {q["sheet"]} of {len(order)}</span><span class="n">{esc(q["name"])}</span></a>'
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
    pl = p["plain"]
    tr = p["try"]
    has_bench = "bench" in f
    try_btn = f'<a class="btn" href="#try">{esc(tr["kind"])}</a> ' if has_bench else ""
    if has_bench:
        bench = bench.replace('<section class="bench"', f'<section class="bench" id="try"', 1)
        bench = (f'<div class="try-head"><h2>{esc(tr["kind"])}</h2><p>{esc(tr["text"])}</p></div>\n' + bench)
    return f"""<div class="sheet">
<header class="title">
<h1>{esc(p["name"])}</h1>
<dl class="plain">
<div><dt>What it does</dt><dd>{esc(pl["what"])}</dd></div>
<div><dt>Why it matters</dt><dd>{esc(pl["why"])}</dd></div>
<div class="pf"><dt>What was found</dt><dd>{esc(pl["found"])}</dd></div>
</dl>
<p class="row cta">{try_btn}<a class="btn alt" href="#limits">Read the limits</a></p>
<ul class="linkrow">{links}</ul>
{note}
</header>
{reading_band(ctx, p)}
{bench}
{glance(p)}
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
<h2 id="limits-h"><span class="label sec-label">Limits</span>What these numbers do not show</h2>
{ex(f["limits"])}
</section>
{trace(ctx, p, ex(f.get("trace", "")))}
{sheets(ctx, p)}
</div>"""
