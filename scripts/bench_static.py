"""Static (no-JS) record of the sinkline Sanitizer switch, generated from assets/data/bench-sinkline.json.

The data file is written by scripts/capture_sinkline_bench.py from real `sinkline scan` runs. This module only
formats it; the live bench (assets/js/bench-sinkline.js) shows the same recorded values one at a time.
"""
from __future__ import annotations

import json
from html import escape as esc
from pathlib import Path

import components as C

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data" / "bench-sinkline.json"


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def facts(v: dict) -> str:
    f = v["findings"][0] if v["findings"] else None
    head = f'{f["rule_id"]}, {f["cwe"]}, {f["severity"]}, confidence {f["confidence"]}' if f else "no rule fired"
    return f"{head}. Exit status {v['status']}."


def sanitizer_note(v: dict) -> str:
    f = v["findings"][0] if v["findings"] else None
    if not f:
        return ""
    for s in f["route"]:
        if s["kind"] == "sanitizer":
            return f'Recorded sanitizer step: {s["note"]}. The finding is {f["cwe"]}.'
    return ""


def pre(label: str, text: str) -> str:
    return f'<pre data-label="{esc(label, quote=True)}" tabindex="0"><code>{esc(text)}</code></pre>'


def sinkline_static() -> str:
    d = load()
    pv = d["provenance"]
    parts = ['<p class="sw-lead">Recorded, not live. All nine runs are listed here; with JavaScript on, a switch shows one at a time.</p>']
    for ex in d["examples"]:
        parts.append(f'<div class="sw-ex" role="group" aria-labelledby="sws-{ex["id"]}">'
                     f'<p class="sw-eh" id="sws-{ex["id"]}"><b>{esc(ex["title"])} ({esc(ex["cwe"])})</b></p>')
        for v in ex["variants"]:
            kind, text = ("fail", "Finding") if v["findings"] else ("pass", "No finding")
            chg = ""
            if v["changed"]:
                chg = "Lines that differ from the unsafe version: " + ", ".join(str(n) for n in v["changed"]) + "."
            note = sanitizer_note(v)
            extra = " ".join(x for x in (chg, note) if x)
            cmd = pv["command"].replace("FILE", v["file"])
            parts.append(
                '<div class="sw-v">'
                f'<p class="sw-vh">{C.stamp(kind, text)} <b>{esc(v["label"])}</b> <span class="sw-facts">{esc(facts(v))}</span></p>'
                + (f'<p class="sw-note">{esc(extra)}</p>' if extra else "")
                + pre(v["file"], v["code"])
                + pre("$ " + cmd, v["out"])
                + "</div>")
        parts.append("</div>")
    return "\n".join(parts)


def sinkline_caption() -> str:
    pv = load()["provenance"]
    return (
        "<b>A sanitizer clears a finding only for its own bug class: <code>shlex.quote</code> clears command injection "
        "and leaves SQL injection and XSS reported, and <code>html.escape</code> leaves command injection reported.</b> "
        f"Recorded, not live: every output is the unedited output of <code>{esc(pv['command'])}</code> "
        f"(sinkline {esc(pv['version'])}, tag v{esc(pv['version'])}, commit {esc(pv['commit'])}) on the file shown, run {esc(pv['captured'])}. "
        "The page runs no analysis; the switch only chooses which recorded output to show. Files, outputs and the capture script: "
        '<a href="https://github.com/samiali38183/samiali38183.github.io/tree/main/assets/data/sinkline-bench">assets/data/sinkline-bench</a>, '
        '<code>scripts/capture_sinkline_bench.py</code>. Two unsafe files were missed by older versions, checked by running them: 0.4.0 reports nothing on the try/except file (join fix in 0.4.1) and 0.4.1 reports nothing on the XSS file, which returns a call result (fix in 0.5.0).'
    )


# ---------------------------------------------------------------------------------------------
# kev-risk-prioritization: Weight bench (no-JS state) and the real-snapshot plate. Both are generated from the data files
# that the live bench, the parity test and check_facts.py use, so the page cannot drift from them.
# ---------------------------------------------------------------------------------------------
def _kev_data() -> tuple[dict, dict, dict]:
    d = json.loads((ROOT / "assets/data/bench-kev-risk.json").read_text(encoding="utf-8"))
    p = json.loads((ROOT / "assets/data/kev-bench-parity.json").read_text(encoding="utf-8"))
    s = json.loads((ROOT / "assets/data/kev-snapshot.json").read_text(encoding="utf-8"))
    return d, p, s


def kev_risk_static() -> str:
    d, p, _ = _kev_data()
    F, top = d["findings"], d["top"]
    pre = {c["g"]: c for c in p["cases"][:4]}
    wrows = []
    for pr in d["presets"]:
        c = pre[pr["k"]]
        n = sum(F[i][6] for i in c["o"][:top])
        w = " / ".join(f"{x:g}" for x in pr["w"])
        best = f'<b class="best">{n}</b>' if n == top else str(n)
        wrows.append(f'<tr><th scope="row">{esc(pr["l"])}</th><td class="num">{w}</td><td class="num">{best}</td>'
                     f'<td class="num">{top - n}</td></tr>')
    presets = (f'<div class="scroll"><table class="tbl"><caption>KEV findings among the top {top} of 20 synthetic findings, by weights</caption>'
               '<thead><tr><th scope="col">Weights</th><th scope="col" class="num">KEV / ACR / EPSS / CVSS</th>'
               f'<th scope="col" class="num">KEV in the top {top}</th><th scope="col" class="num">Non-KEV in the top {top}</th></tr></thead><tbody>'
               + "".join(wrows) + "</tbody></table></div>")
    d0 = pre["default"]
    rows = []
    for rank, (i, sc) in enumerate(zip(d0["o"], d0["s"]), 1):
        cve, asset, acr, cvss, epss, days, kev = F[i]
        cut = ' class="cut"' if rank == top + 1 else ""
        rows.append(f'<tr{cut}><th scope="row" class="num">{rank}</th><td>{esc(cve)}</td><td>{esc(asset)}</td><td>{"KEV" if kev else "no"}</td>'
                    f'<td class="num">{cvss:.1f}</td><td class="num">{epss:.3f}</td><td class="num">{acr:g}</td><td class="num">{days}</td>'
                    f'<td class="num">{sc:.1f}</td></tr>')
    ranked = ('<section class="scroll wb-scroll" tabindex="0" aria-label="Default ranking, scrolls sideways on narrow screens"><table class="wb-t">'
              f'<caption>The 20 synthetic findings ranked with the default weights (0.40 / 0.25 / 0.20 / 0.20), as the tool prints them. A line marks the end of the top {top}.</caption>'
              '<thead><tr><th scope="col">Rank</th><th scope="col">CVE</th><th scope="col">Asset</th><th scope="col">KEV</th>'
              '<th scope="col" class="num">CVSS</th><th scope="col" class="num">EPSS</th><th scope="col" class="num">ACR</th>'
              '<th scope="col" class="num">Days open</th><th scope="col" class="num">Risk score</th></tr></thead><tbody>'
              + "".join(rows) + "</tbody></table></section>")
    return '<p class="sw-lead">Recorded state. With JavaScript on, four sliders re-rank the same 20 findings.</p>' + presets + ranked


def kev_risk_caption() -> str:
    d, _, _ = _kev_data()
    m = d["meta"]
    k = m["kev_in_top"]
    return (f'<b>With the default weights all 12 KEV findings are in the top 12; a CVSS-only sort puts {k["cvss"]} there.</b> '
            "The 20 findings are the tool's synthetic demo: real KEV CVE IDs with invented assets, ACR, EPSS, CVSS and ages. "
            "It shows how the formula orders findings under different weights. It does not show that any weighting improves remediation, "
            "and the default result is largely by construction, since the KEV weight (0.40) equals the EPSS and CVSS weights combined. "
            f'Scores come from kev-risk-prioritization {esc(m["tag"])} (commit {esc(m["commit"])}); the page re-implements the formula and '
            f'<code>scripts/test_bench_kev.mjs</code> checks it against the tool on {m["parity_cases"]} weight vectors.')


def _n(x: int) -> str:
    return f"{x:,}"


def kev_snapshot_plate() -> str:
    """Static SVG: share of CVEs at or above each EPSS value, KEV vs sampled non-KEV, with a text-equivalent table."""
    from math import log10
    _, _, s = _kev_data()
    m, th = s["meta"], s["thresholds"]
    W, H, L, R, T, B = 560, 330, 52, 16, 30, 44
    pw, ph = W - L - R, H - T - B

    def xp(v: float) -> float:
        return L + (log10(v) + 3) / 3 * pw

    def yp(f: float) -> float:
        return T + (1 - f) * ph

    pts = lambda arr: " ".join(f"{L + i / 60 * pw:.1f},{yp(f):.1f}" for i, f in enumerate(arr))  # noqa: E731
    g = []
    for f in (0, .25, .5, .75, 1):
        g.append(f'<line class="g" x1="{L}" x2="{W - R}" y1="{yp(f):.1f}" y2="{yp(f):.1f}"/>'
                 f'<text class="t" x="{L - 6}" y="{yp(f) + 4:.1f}" text-anchor="end">{int(f * 100)}%</text>')
    for v, lab in ((0.001, "0.001"), (0.01, "0.01"), (0.1, "0.1"), (1, "1")):
        g.append(f'<line class="g" x1="{xp(v):.1f}" x2="{xp(v):.1f}" y1="{T}" y2="{T + ph}"/>'
                 f'<text class="t" x="{xp(v):.1f}" y="{T + ph + 16}" text-anchor="middle">{lab}</text>')
    marks = []
    for t in ("0.1", "0.5", "0.9"):
        x = xp(float(t))
        k = th[t]
        side = {"0.1": (-8, 20, "end"), "0.5": (8, -8, "start"), "0.9": (-8, 4, "end")}[t]
        marks.append(f'<line class="thr" x1="{x:.1f}" x2="{x:.1f}" y1="{T - 6}" y2="{T + ph}"/>'
                     f'<text class="t b" x="{x:.1f}" y="{T - 10}" text-anchor="middle">{t}</text>'
                     f'<rect class="pt" x="{x - 4:.1f}" y="{yp(k["kev_pct"] / 100) - 4:.1f}" width="8" height="8"/>'
                     f'<text class="t b" x="{x + side[0]:.1f}" y="{yp(k["kev_pct"] / 100) + side[1]:.1f}" '
                     f'text-anchor="{side[2]}">{k["kev_pct"]}%</text>')
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="ksn-t ksn-d">'
           '<title id="ksn-t">Share of CVEs at or above each EPSS value, KEV against sampled non-KEV</title>'
           f'<desc id="ksn-d">Two falling curves on a log scale from 0.001 to 1. KEV curve: {th["0.1"]["kev_pct"]}% of KEV CVEs have EPSS 0.1 or higher, '
           f'{th["0.5"]["kev_pct"]}% have 0.5 or higher, {th["0.9"]["kev_pct"]}% have 0.9 or higher. Sampled non-KEV curve: {th["0.1"]["sample_pct"]}%, '
           f'{th["0.5"]["sample_pct"]}% and {th["0.9"]["sample_pct"]}% at the same thresholds. The table below gives the same numbers.</desc>'
           + "".join(g) + f'<polyline class="c2" points="{pts(s["non_kev"])}"/><polyline class="c1" points="{pts(s["kev"])}"/>'
           + "".join(marks)
           + f'<text class="t b" x="{xp(0.005):.1f}" y="{yp(.85):.1f}">KEV, {_n(m["kev_rows"])} CVEs</text>'
           f'<text class="t b" x="{xp(0.0015):.1f}" y="{yp(.3):.1f}">Sampled non-KEV,</text>'
           f'<text class="t b" x="{xp(0.0015):.1f}" y="{yp(.3) + 16:.1f}">{_n(m["non_kev_rows"])} CVEs</text>'
           f'<text class="t" x="{L + pw / 2:.1f}" y="{H - 6}" text-anchor="middle">EPSS value (log scale)</text></svg>')
    rows = []
    for t in ("0.1", "0.5", "0.9"):
        k = th[t]
        rows.append(f'<tr><th scope="row" class="num">at or above {t}</th><td class="num">{_n(k["kev"])} ({k["kev_pct"]}%)</td>'
                    f'<td class="num">{_n(k["sample"])} ({k["sample_pct"]}%)</td><td class="num">{_n(k["pop_non_kev"])}</td>'
                    f'<td class="num">{k["precision_pct"]}%</td></tr>')
    table = (f'<div class="scroll"><table class="tbl"><caption>Text equivalent of the figure: CVEs at or above each EPSS value</caption><thead><tr>'
             f'<th scope="col" class="num">EPSS at or above</th><th scope="col" class="num">KEV CVEs (of {_n(m["kev_rows"])})</th>'
             f'<th scope="col" class="num">Sampled non-KEV (of {_n(m["non_kev_rows"])})</th>'
             f'<th scope="col" class="num">All non-KEV in the EPSS file (of {_n(m["non_kev_population"])})</th>'
             '<th scope="col" class="num">Flagged CVEs that are KEV, at population prevalence</th></tr></thead><tbody>'
             + "".join(rows) + "</tbody></table></div>")
    cap = (f'<b>EPSS is high for most KEV CVEs and low for most others: AUC {s["auc"]} (95% bootstrap interval {s["auc_lo"]} to {s["auc_hi"]}).</b> '
           f'Median EPSS is {s["median"]["kev"]} for KEV and {s["median"]["non_kev"]} for the sample. EPSS is partly trained on exploitation evidence that overlaps with KEV, '
           "so this is two related signals agreeing, not independent validation of either, and it does not test the risk score. "
           f'Drawn from {_n(m["rows"])} rows of the committed EPSS subset (all {_n(m["kev_rows"])} KEV CVEs plus {_n(m["non_kev_rows"])} seeded non-KEV CVEs); '
           f'KEV catalog {esc(m["kev_catalog"])}, EPSS file {esc(m["epss_date"])}, model {esc(m["epss_model"])}.')
    return (f'<figure class="plate snap"><span class="plate-label">Plate {{{{n}}}}</span><div class="snapfig">{svg}</div>{table}'
            f'<figcaption>{cap}</figcaption></figure>')
