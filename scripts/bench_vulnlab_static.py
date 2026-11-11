"""Static (no-JS) record of the vulnlab Lab explorer, generated from assets/data/vulnlab-bench.json.

The data file is written by scripts/capture_vulnlab_bench.py from a real run of vulnlab v0.1.0. This module only formats it:
a summary table of all six lab and version pairs, then one `details` per lab holding the code, tests, sinkline output and
detection replay for both versions. The live bench (assets/js/bench-vulnlab.js) shows the same recorded values one pair at a time.
"""
from __future__ import annotations

import json
from html import escape as esc
from pathlib import Path

import components as C

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data" / "vulnlab-bench.json"

# Same wording as READING in assets/js/bench-vulnlab.js (scripts/test_bench_vulnlab.mjs checks the page against the module).
READING = {
    "true positive": "Correct: the finding is the bug.",
    "false positive": "False positive: this version is fixed.",
    "missed": "Not reported. The write-up expects this: a missing check is not a taint flow.",
    "clean": "Nothing to report on the fixed version.",
}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def pre(label: str, text: str) -> str:
    return f'<pre data-label="{esc(label, quote=True)}" tabindex="0"><code>{esc(text)}</code></pre>'


def sink_facts(s: dict) -> str:
    n = len(s["findings"])
    head = "; ".join(f'{f["rule_id"]}, {f["cwe"]}, {f["severity"]}, app.py:{f["line"]}' for f in s["findings"]) if n else "no rule fired"
    return f"{head}. Exit status {s['status']}."


def totals(v: dict) -> tuple[int, int]:
    return sum(t["passed"] for t in v["tests"]), sum(t["cases"] for t in v["tests"])


def summary_table(d: dict) -> str:
    rows = []
    for lab in d["labs"]:
        det = lab["detection"]
        for v in lab["versions"]:
            p, c = totals(v)
            s = v["sinkline"]
            kind, text = ("fail", "Impact demonstrated") if v["id"] == "vulnerable" else ("pass", "Impact blocked")
            skind, stext = ("plain", "Finding") if s["findings"] else ("off", "No finding")
            rows.append(
                f'<tr><th scope="row"><span class="label">Lab {lab["n"]}</span><br>{esc(lab["title"])} ({esc(lab["cwe"])})<br><b>{esc(v["label"])}</b></th>'
                f'<td>{C.stamp(kind, text)}<p>{p} of {c} tests passed</p></td>'
                f'<td>{C.stamp(skind, stext)}<p>{esc(READING[s["reading"]])}</p></td>'
                f'<td><p>Attack sample: {det["attack"]["events"]} events, {_plural(det["attack"]["alerts"], "alert")}.</p>'
                f'<p>Benign sample: {det["benign"]["events"]} events, {_plural(det["benign"]["alerts"], "alert")}.</p></td></tr>')
    return ('<div class="scroll wide"><table class="tbl bt"><caption>Recorded results for each lab and version: its own tests, sinkline, '
            'and the detection replay</caption>'
            '<thead><tr><th scope="col">Lab and version</th><th scope="col">Its tests</th><th scope="col">sinkline</th>'
            '<th scope="col">Detection replay (same for both versions)</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def version_block(d: dict, lab: dict, v: dict) -> str:
    roles = d["roles"]
    p, c = totals(v)
    s = v["sinkline"]
    marks = []
    if v["marks"]["bug"]:
        marks.append("Vulnerable line the write-up names: " + ", ".join(map(str, v["marks"]["bug"])) + ".")
    if v["marks"]["changed"]:
        marks.append("Lines that are not in the vulnerable version: " + ", ".join(map(str, v["marks"]["changed"])) + ".")
    flow = []
    for f in s["findings"]:
        flow.append("sinkline path: " + ", ".join(f'{x["kind"]} line {x["line"]}' for x in f["flow"]) + ".")
    kind, text = ("fail", "Impact demonstrated") if v["id"] == "vulnerable" else ("pass", "Impact blocked")
    skind, stext = ("plain", "Finding") if s["findings"] else ("off", "No finding")
    trows = "".join(
        f'<tr><th scope="row"><code>{esc(t["name"])}</code></th><td>{esc(roles[t["role"]])}</td>'
        f'<td>{C.stamp("pass" if t["passed"] == t["cases"] else "fail", ("Pass" if t["passed"] == t["cases"] else "Fail") + (f" ({t["passed"]} of {t["cases"]} cases)" if t["cases"] > 1 else ""))}</td></tr>'
        for t in v["tests"])
    return (
        f'<section class="vl-sv" data-lab="{esc(lab["id"])}" data-ver="{esc(v["id"])}" aria-labelledby="vls-{esc(lab["id"])}-{v["id"]}">'
        f'<h4 class="vl-vh" id="vls-{esc(lab["id"])}-{v["id"]}">{esc(v["label"])}</h4>'
        f'<p class="sw-vh">{C.stamp(kind, text)} <span class="vl-say">{esc(v["outcome"])}</span></p>'
        f'<p class="sw-note">{esc(v["summary"])}</p>'
        f'<p class="sw-note">{" ".join(esc(x) for x in marks + flow)}</p>'
        + pre(v["file"], v["code"])
        + f'<p class="sw-note">{p} of {c} test cases passed in this version.</p>'
        '<div class="scroll wide"><table class="tbl bt"><caption>Recorded results of the tests that belong to this version</caption>'
        '<thead><tr><th scope="col">Test</th><th scope="col">What it shows</th><th scope="col">Result</th></tr></thead>'
        f'<tbody>{trows}</tbody></table></div>'
        f'<p class="sw-vh">{C.stamp(skind, stext)} <span class="sw-facts">{esc(sink_facts(s))}</span></p>'
        f'<p class="sw-note">{esc(READING[s["reading"]] + (" " + s["note"] if s["note"] else ""))}</p>'
        + pre("$ " + s["command"], s["out"])
        + "</section>")


def detection_block(lab: dict) -> str:
    det = lab["detection"]
    corr = det["correlation"]
    rule = " / ".join(det["titles"]) + (
        f' (correlation: {corr["type"]} of {corr["field"]} by {corr["group_by"]}, {corr["gte"]} or more in {corr["timespan"]})' if corr else "")
    rows = []
    for key, label in (("attack", "Attack sample"), ("benign", "Benign sample")):
        r = det[key]
        rk, rt = ("plain", "Alert") if r["alerts"] else ("off", "No alert")
        rows.append(f'<tr><th scope="row">{label} (recorded from the {esc(r["from"])} service)</th>'
                    f'<td>{r["events"]} events, {_plural(r["alerts"], "alert")}</td><td>{C.stamp(rk, rt)}</td></tr>')
    test = det["test"]
    return (
        f'<section class="vl-sv" data-lab="{esc(lab["id"])}" data-ver="detection" aria-labelledby="vls-{esc(lab["id"])}-det">'
        f'<h4 class="vl-vh" id="vls-{esc(lab["id"])}-det">Detection replay</h4>'
        f'<p class="sw-note">Rule: {esc(rule)}. {esc(test["name"])}: {"Pass" if test["passed"] == test["cases"] else "Fail"}.</p>'
        '<div class="scroll wide"><table class="tbl bt"><caption>The rule replayed over two recorded access logs</caption>'
        '<thead><tr><th scope="col">Sample</th><th scope="col">Events and alerts</th><th scope="col">Result</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        + pre("$ python -m vulnlab_common.replay RULE LOG", det["attack"]["out"] + det["benign"]["out"])
        + "</section>")


def vulnlab_static() -> str:
    d = load()
    parts = ['<p class="sw-lead">Recorded, not live. All six lab and version pairs are listed here; with JavaScript on, a two-part switch shows one at a time.</p>',
             summary_table(d)]
    for lab in d["labs"]:
        inner = "".join(version_block(d, lab, v) for v in lab["versions"]) + detection_block(lab)
        parts.append(f'<details class="alt vl-lab"><summary>Lab {lab["n"]}, {esc(lab["title"])}: code, tests, sinkline and detection for both versions</summary>{inner}</details>')
    return "\n".join(parts)


def vulnlab_caption() -> str:
    d = load()
    pv = d["provenance"]
    return (
        "<b>Each fix stops the impact its lab's own tests show on the vulnerable service. The other checks agree less: sinkline reports the two "
        "injection-style bugs and also their fixed versions, nothing on the missing-authorization bug, and the detection rules alert on the attempts "
        "whether or not the service is fixed.</b> "
        f"Recorded, not live: every result is output of a real run of <code>{esc(pv['tool'])}</code> {esc(pv['tag'])} "
        f"(commit {esc(pv['commit'])}) on {esc(pv['captured'])}: Python {esc(pv['python'])}, pytest {esc(pv['pytest'])}, sinkline {esc(pv['sinkline'])}, "
        f"tripline {esc(pv['tripline'])}, pySigma {esc(pv['pysigma'])}, {esc(pv['os'])}; "
        f"<code>{esc(pv['commands']['tests'])}</code>, then sinkline and the Sigma replay per lab. "
        "The page evaluates nothing; the switch only chooses which recorded result to show. "
        "Everything ran against the lab's own services on loopback. Regenerate with <code>python scripts/capture_vulnlab_bench.py</code>; "
        "<code>node scripts/test_bench_vulnlab.mjs</code> checks that the page shows exactly the stored data.")
