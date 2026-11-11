"""HTML components generated at build time: ruler strips, stamps, evidence chips, diagrams, table labels.

Pure functions returning strings. No dependencies. See docs/DESIGN_SYSTEM.md for the markup each one emits.
"""
from __future__ import annotations

import html
import re
from typing import Iterable

esc = html.escape

# ---------------------------------------------------------------------------------------------
# Ruler strip
# ---------------------------------------------------------------------------------------------
# States: hit = observed (filled), miss = expected but missed (hatched), neg = not expected (outline),
# pend = pending (dotted outline), fp = reported where nothing was expected (half filled).
STATES = ("hit", "miss", "neg", "pend", "fp")
Runs = list[tuple[str, int]]


def expand(runs: Runs) -> list[str]:
    out: list[str] = []
    for state, n in runs:
        assert state in STATES, state
        out.extend([state] * n)
    return out


def normalize(runs: Runs, ticks: int = 24) -> Runs:
    """Scale run lengths to at most `ticks` ticks, keeping every non-empty run visible. Exact when the total fits."""
    total = sum(n for _, n in runs)
    if total <= ticks:
        return list(runs)
    sizes = [max(1, round(n * ticks / total)) for _, n in runs]
    while sum(sizes) != ticks:
        i = max(range(len(sizes)), key=lambda k: sizes[k]) if sum(sizes) > ticks else \
            max(range(len(sizes)), key=lambda k: runs[k][1] * ticks / total - sizes[k])
        sizes[i] += -1 if sum(sizes) > ticks else 1
    return [(s, n) for (s, _), n in zip(runs, sizes)]


def describe(label: str, unit: str, runs: Runs, phr: dict[str, str]) -> str:
    total = sum(n for _, n in runs)
    merged: dict[str, int] = {}
    for s, n in runs:
        merged[s] = merged.get(s, 0) + n
    parts = ", ".join(f"{n} {phr.get(s, s)}" for s, n in merged.items())
    return f"{label}, {total} {unit}: {parts}"


def strip(runs: Runs, label: str, unit: str, phr: dict[str, str], mini: bool = False, true_runs: Runs | None = None) -> str:
    """One strip. `runs` are drawn; `true_runs` (default `runs`) supply the accessible description."""
    states = expand(runs)
    aria = describe(label, unit, true_runs or runs, phr)
    ticks = []
    for i, s in enumerate(states, 1):
        major = (not mini) and i % 10 == 0
        extra = ' class="m" data-n="%d"' % i if major else ""
        ticks.append('<i data-s="%s"%s></i>' % (s, extra))
    return f'<div class="strip" role="img" aria-label="{esc(aria, quote=True)}">{"".join(ticks)}</div>'


def strip_rows(sset: dict, mini: bool = False, vt: str | None = None, show_val: bool = True) -> str:
    """A pair (or single row) of strips from a project's strip set."""
    rows = []
    for r in sset["rows"]:
        runs = [tuple(x) for x in r["runs"]]
        drawn = normalize(runs, 24) if mini else runs
        val = f'<p class="val">{r["val"]}</p>' if (show_val and not mini and r.get("val")) else ""
        rows.append(
            f'<div class="srow"><span class="label" aria-hidden="true">{esc(r["label"])}</span>'
            f'{strip(drawn, r["label"], sset["unit"], sset["phr"], mini, runs)}{val}</div>')
    cls = "strips mini" if mini else "strips"
    if vt:
        cls += " vt"
    style = f' style="--vt:{vt}"' if vt else ""
    return f'<div class="{cls}"{style}>{"".join(rows)}</div>'


def key(sset: dict) -> str:
    """Legend: shape plus words for every state the strip set uses."""
    used = []
    for r in sset["rows"]:
        for s, _ in r["runs"]:
            if s not in used:
                used.append(s)
    items = "".join(
        f'<li><span class="strip" aria-hidden="true"><i data-s="{s}"></i></span>{esc(sset["phr"].get(s, s))}</li>' for s in used)
    note = f'<li>{esc(sset["note"])}</li>' if sset.get("note") else ""
    return f'<ul class="key" aria-label="How to read the strips">{items}{note}</ul>'


# ---------------------------------------------------------------------------------------------
# Verdict stamp and evidence chip
# ---------------------------------------------------------------------------------------------
def stamp(kind: str, text: str) -> str:
    assert kind in ("fail", "pass", "limit", "pend", "plain"), kind
    cls = "stamp" + ("" if kind == "plain" else f" {kind}")
    return f'<span class="{cls}">{esc(text)}</span>'


def chip(run_id: str, runs: dict) -> str:
    r = runs[run_id]
    state = {"success": "pass", "failure": "fail"}.get(r["conclusion"], "pend")
    word = {"success": "passed", "failure": "failed"}.get(r["conclusion"], r["conclusion"] or "pending")
    href = f'https://github.com/samiali38183/{r["repo"]}/actions/runs/{run_id}'
    return (f'<a class="chip" data-s="{state}" href="{href}"><span class="st" aria-hidden="true"></span>'
            f'<span>run {run_id}</span> <span class="d">{word} {r["date"]}</span></a>')


# ---------------------------------------------------------------------------------------------
# Diagrams: hand-written inline SVG, mono labels, square corners, orthogonal connectors, open arrowheads.
# ---------------------------------------------------------------------------------------------
DIAGRAMS = {
    "fuzzdiff": ("fuzzdiff differential harness", "Fuzzer or test bytes are decoded into a case. The same case runs through the C original, which is compiled with sanitizers and fed exact-size heap copies, and through the safe Rust port. The harness compares the two results and classifies them as Equal, BothReject, RustStricter or Divergence.", [
        ("box", "Input bytes", "corpus, generator, proptest, libFuzzer"),
        ("box", "Decode into a case", "entry point, header capacity, last_len, chunk splits"),
        ("box", "C original and Rust port, same case", "C: exact-size heap copy, ASan and UBSan. Rust: safe"),
        ("hi", "compare()", "consumed length, fields, decoded bytes"),
        ("box", "Equal, BothReject, RustStricter (D1, D2)", "expected outcomes"),
        ("warn", "Divergence", "a bug in one side; fails the tests and the CI fuzz job"),
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
        ("box", "Fixtures committed to the repo", "run.ndjson and manifest.json, reviewed by a person"),
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


def wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def diagram(key_: str, number: int | None = None) -> str:
    """A diagram plate: SVG with title, desc and an adjacent text alternative."""
    title, desc, boxes = DIAGRAMS[key_]
    vb_w, x0, bw, gap = 320, 26, 290, 26
    y = 4
    parts: list[str] = []
    alt: list[str] = []
    for i, (kind, a, b) in enumerate(boxes):
        tl, sl = wrap(a, 30), wrap(b, 33)
        h = 14 + 19 * len(tl) + 17 * len(sl) + 10
        cls = {"box": "", "hi": ' class="hi"', "warn": ' class="warn"'}[kind]
        parts.append(f'<rect{cls} x="{x0}" y="{y}" width="{bw}" height="{h}"/>')
        if kind == "warn":
            parts.append(f'<path class="hatch-line" d="M{x0} {y + h} l{min(h, 20)} -{min(h, 20)} M{x0} {y + h - 8} l8 -8 M{x0 + 8} {y + h} l{min(h, 20) - 8} -{min(h, 20) - 8}"/>')
        ty = y + 22
        tx = x0 + 12
        for ln in tl:
            parts.append(f'<text x="{tx}" y="{ty}" font-weight="600" font-size="14">{esc(ln)}</text>')
            ty += 19
        for ln in sl:
            parts.append(f'<text class="sub" x="{tx}" y="{ty - 1}" font-size="13">{esc(ln)}</text>')
            ty += 17
        letter = chr(65 + i)
        parts.append(f'<circle class="letter" cx="{x0 - 14}" cy="{y + 12}" r="9"/><text class="lt" x="{x0 - 14}" y="{y + 16}">{letter}</text>')
        alt.append(f"<li><strong>{esc(a)}.</strong> {esc(b)}.</li>")
        if i < len(boxes) - 1:
            ax = x0 + bw // 2
            y1, y2 = y + h, y + h + gap
            parts.append(f'<path class="arrow" d="M{ax} {y1} V{y2 - 1}"/><path class="head" d="M{ax - 5} {y2 - 8} L{ax} {y2 - 1} L{ax + 5} {y2 - 8}"/>')
        y += h + gap
    height = y - gap + 4
    svg = (f'<svg viewBox="0 0 {vb_w} {height}" role="img" aria-labelledby="{key_}-t {key_}-d">'
           f'<title id="{key_}-t">{esc(title)}</title><desc id="{key_}-d">{esc(desc)}</desc>{"".join(parts)}</svg>')
    label = '<span class="plate-label">Plate {{n}}</span>'
    return (f'<figure class="plate diagram">{label}{svg}<figcaption>{esc(desc)}</figcaption></figure>'
            f'<details class="alt"><summary>Describe this diagram</summary><ol class="alt-list" type="A">{"".join(alt)}</ol></details>')


# ---------------------------------------------------------------------------------------------
# Tables: add data-label to cells so the table can collapse to cards on phones.
# ---------------------------------------------------------------------------------------------
_TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)


def label_tables(page: str) -> str:
    def one(m: re.Match) -> str:
        t = m.group(0)
        head = re.search(r"<thead>.*?</thead>", t, re.S)
        if not head:
            return t
        names = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<th\b[^>]*>(.*?)</th>", head.group(0), re.S)]
        body_start = head.end()
        body = t[body_start:]

        def row(r: re.Match) -> str:
            idx = {"i": 0}

            def cell(c: re.Match) -> str:
                tag, attrs = c.group(1), c.group(2)
                i = idx["i"]
                idx["i"] += 1
                if tag == "td" and "data-label" not in attrs and i < len(names):
                    return f'<td{attrs} data-label="{esc(names[i], quote=True)}">'
                return c.group(0)
            return re.sub(r"<(td|th)\b([^>]*)>", cell, r.group(0))
        body = re.sub(r"<tr\b.*?</tr>", row, body, flags=re.S)
        return t[:body_start] + body
    return _TABLE.sub(one, page)
