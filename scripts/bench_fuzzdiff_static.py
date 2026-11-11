"""Static (no-JS) record of the fuzzdiff "Side-by-side parser" bench and its seeded-bug panel.

Generated from assets/data/fuzzdiff-bench.json, which scripts/capture_fuzzdiff_bench.py writes from real runs of
picohttpparser (C), fuzzdiff (Rust) and httparse. The result text here must equal what assets/js/bench-fuzzdiff.js
shows; scripts/test_bench_fuzzdiff.mjs checks both against the JSON.
"""
from __future__ import annotations

import json
import math
import re
from html import escape as esc
from pathlib import Path

import components as C

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data" / "fuzzdiff-bench.json"
SHOW = 240

MUTANTS = {
    "HeaderLenOffByOne": "A header value longer than 16 bytes comes back one byte short.",
    "MissingBoundsCheck": "The end-of-buffer guard after HTTP/1.x is missing, so a head cut right after the version reads one byte too far (a panic in Rust).",
    "WrongStateAfterCrlf": "After a trailer line the chunked decoder goes to the wrong state and never sees the blank line that ends the trailers.",
    "OverheadRatio": "The framing-overhead guard fires at 80% instead of 75%; it needs more than 100 KiB of chunk framing to matter.",
    "StatusGuard": "The response parser waits for 3 bytes after the status-line spaces instead of 4.",
}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def lines(r: dict | None, op: str) -> list[str]:
    if not r:
        return ["not run (see the note)"]
    v = r["verdict"]
    if v == "partial":
        return ["partial (needs more bytes)"]
    if v == "panic":
        return ["panic (the parser panicked)"]
    if v == "error":
        return ["error" + (f" ({r['error']})" if r.get("error") else "")]
    if op == "chunked":
        if "size" in r:
            return [f"complete (size line {r['consumed']} bytes, size {r['size']})"]
        return ["complete", f'decoded "{r["decoded"]}" ({r["decoded_len"]} bytes)', f'leftover "{r["leftover"]}" ({r["leftover_len"]} bytes)']
    out = [f"complete (consumed {r['consumed']} bytes)"]
    if op == "request":
        out.append(f'method "{r["method"]}", target "{r["target"]}", HTTP/1.{r["minor"]}')
    if op == "response":
        out.append(f'HTTP/1.{r["minor"]}, status {r["status"]}, reason "{r["reason"]}"')
    n = r["nheaders"]
    out.append(f"{n} header" + ("" if n == 1 else "s"))
    for nm, val in r["headers"]:
        out.append(f"{'(no name)' if nm is None else nm}: {val}")
    if n > len(r["headers"]):
        out.append(f"+{n - len(r['headers'])} more")
    return out


def shown_bytes(i: dict) -> tuple[str, str]:
    if len(i["bytes"]) > SHOW:
        return i["bytes"][:SHOW] + "…", f"First {SHOW} characters of the escaped bytes shown; {i['bytes_len']} bytes in total."
    return i["bytes"], ""


def harness(i: dict) -> tuple[str, str, str]:
    h = i["harness"]
    if h["kind"] == "Equal":
        return "pass", "Equal", "C and Rust returned the same result."
    if h["kind"] == "BothReject":
        return "plain", "BothReject", "Both rejected the input."
    if h["kind"] == "RustStricter":
        return "limit", f"RustStricter ({h['deviation']})", "Rust rejects what C accepts, by a documented deviation (D1: optional rejection of folded header lines, switched on for this input)."
    return "fail", f"Divergence ({h['how']})", "The two results differ, so the harness reports a bug. Here the bug is the seeded one named in the title."


def relation(i: dict) -> str:
    if i["mutant"]:
        return "Shown for reference only. The seeded bug is in the Rust column, so no pattern is classified."
    if i["pattern"] is None:
        return ""
    base = f"Pattern {i['pattern']} (picohttpparser, fuzzdiff, httparse; C complete, P partial, R reject; ! fields differ). "
    d = i["doc"]
    if d:
        tail = "The three parsers behave alike here." if d["stricter"] == "same" else f"Stricter: {d['stricter']}."
        return base + f"Documented class: {d['class']} ({d['rfc']}). " + tail + (" The pattern is for the default configuration; this input runs Rust in strict mode." if i["strict"] else "")
    if i["explained_by"] == "agree":
        return base + "All three agree."
    return base + f"Explained by {i['explained_by']}."


def parser_static() -> str:
    d = load()
    m = d["meta"]
    rows = []
    for i in d["inputs"]:
        text, note = shown_bytes(i)
        kind, label, htext = harness(i)
        cells = "".join(
            f'<td data-fz="{k}">' + "<br>".join(esc(x) for x in lines(i[key], i["op"])) + "</td>"
            for k, key in (("c", "c"), ("rust", "rust"), ("hp", "httparse")))
        rows.append(
            f'<tr data-fz-id="{i["id"]}"><th scope="row"><span class="label">{esc(i["group"])}</span><br>{esc(i["title"])}'
            f'<br><code data-fz="bytes">{esc(text)}</code>'
            + (f'<br><span class="small muted" data-fz="note">{esc(note)}</span>' if note else "") + "</th>"
            + cells
            + f'<td>{C.stamp(kind, label)}<p data-fz="harness">{esc(htext)}</p><p class="small muted" data-fz="relation">{esc(relation(i))}</p></td></tr>')
    return (
        f'<h2 class="vh">Side-by-side parser</h2><p class="sw-lead">Recorded, not live. All {len(d["inputs"])} inputs are listed here; with JavaScript on, a picker shows one at a time.</p>'
        '<div class="scroll wide"><table class="tbl fz-tbl">'
        f'<caption>What each parser returned for {len(d["inputs"])} inputs, and how the harness classified the C and Rust results</caption>'
        '<thead><tr><th scope="col">Input (bytes with escapes)</th>'
        f'<th scope="col">picohttpparser (C, {esc(m["c_reference"].split()[1])})</th><th scope="col">fuzzdiff (Rust)</th>'
        f'<th scope="col">httparse {esc(m["httparse"].split()[0])}</th><th scope="col">Harness classification and httparse comparison</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>")


def parser_caption() -> str:
    m = load()["meta"]
    return (
        "<b>With default settings picohttpparser and fuzzdiff return the same result on every input here, except the two seeded-bug rows and the strict-mode row (documented deviation D1); httparse, a different parser, differs from both in a fixed set of documented classes.</b> "
        f"Recorded, not live: every result was returned by the parser named, on the bytes shown (fuzzdiff {esc(m['version'])}, tag {esc(m['tag'])}, commit {esc(m['commit'])}; "
        f"picohttpparser {esc(m['c_reference'].split()[1])}; httparse {esc(m['httparse'])}; {m['slots']} header slots for all three; {esc(m['platform'])}), "
        f"run {esc(m['captured'])} with <code>scripts/capture_fuzzdiff_bench.py</code>. The page runs no parser. "
        "The httparse column covers head parsing and, for chunked bodies, only the first chunk-size line. "
        "The two seeded-bug rows run the Rust parser with a test-only bug switched on; the shipped parser has none."
    )


def fmt_time(s: str) -> str:
    v = float(s)
    if v < 0.001:
        return f"{v * 1e6:.0f} µs"
    if v < 1:
        return f"{v * 1e3:.1f} ms"
    return f"{v:.2f} s"


def half_decades(n: int) -> int:
    return max(1, math.ceil(2 * math.log10(n)))


def mutants_panel() -> str:
    d = load()
    budget = d["mutants"][0]["budget"]
    full = half_decades(budget)
    rows, srows = [], []
    for mu in d["mutants"]:
        gi = mu["generator_inputs"]
        gen = f"{gi:,}" if gi is not None else f"not caught in {mu['budget']:,}"
        tgt = f"case {mu['targeted_case']}" if mu["targeted_case"] else "none catches it"
        how = mu["generator_how"] or mu["targeted_how"]
        rows.append(
            f'<tr data-mutant="{esc(mu["name"])}"><th scope="row"><code>{esc(mu["name"])}</code><p class="small muted">{esc(MUTANTS[mu["name"]])}</p></th>'
            f'<td class="num">{gen}</td><td class="num">{fmt_time(mu["generator_seconds"])}</td><td>{tgt}</td><td>{esc(how)}</td></tr>')
        if gi is None:
            runs = [("miss", full)]
            val = f"<b>not caught</b> in {mu['budget']:,} inputs; caught by targeted case {mu['targeted_case']}"
        else:
            k = half_decades(gi)
            runs = [("hit", k)] + ([("neg", full - k)] if full > k else [])
            val = f"caught after <b>{gi:,}</b> inputs"
        srows.append({"label": mu["name"], "runs": runs, "val": val})
    sset = {"unit": "half-decades of inputs", "per": 1, "total_label": "effort until caught", "phr": {
        "hit": "half-decades of generated inputs until the harness caught the bug", "neg": "budget not needed",
        "miss": "half-decades searched without catching it"}, "rows": srows}
    c = d["control"]
    return (
        '<div class="fz-mut"><h3 class="fz-h">Seeded bugs: how much input the harness needed</h3>'
        '<div class="scroll wide"><table class="tbl bt"><caption>Measured detection effort for the five seeded bugs (the mutant test; deterministic generator, seed = input index + 1)</caption>'
        '<thead><tr><th scope="col">Seeded bug</th><th scope="col" class="num">Generator inputs until caught</th><th scope="col" class="num">Generator time</th>'
        '<th scope="col">Targeted case</th><th scope="col">How it showed</th></tr></thead><tbody>' + "".join(rows)
        + f'<tr><th scope="row">Control (no bug seeded)</th><td class="num">{c["inputs"]:,} inputs</td><td class="num">{fmt_time(c["seconds"])}</td>'
        f'<td>{c["targeted_cases"]} targeted cases</td><td>{c["divergences"]} divergences</td></tr>'
        "</tbody></table></div>"
        + C.key(sset) + C.strip_rows(sset)
        + '<p class="small muted">Each tick is a factor of about 3.2 in generated inputs (half a decade), so a short strip means little input was needed; the counts in the table are exact. '
        f'The budget is {budget:,} inputs ({full} ticks). Times are one run on the capture machine and vary; the counts do not. '
        'The three bugs caught in under 300 inputs show the plumbing works; they do not show that every subtle bug would be found.</p></div>')


SWEEP = ROOT / "assets" / "data" / "fuzzdiff-bench" / "sweep-table.md"


def sweep_numbers() -> dict:
    """Headline numbers of the 2,000,000-input sweep, read from the copy of the generated block in docs/DIFFERENTIAL_HTTPARSE.md."""
    t = SWEEP.read_text(encoding="utf-8")
    m = re.search(r"Inputs: (\d+) \((\d+) request, (\d+) response, (\d+) header block\)\. All three parsers did the same thing on (\d+) \(([\d.]+)%\); they disagreed on (\d+)\.", t)
    k = re.search(r"differed on (\d+) inputs.*?explained by no known feature: (\d+)\. .*?earlier: (\d+)\.", t, re.S)
    assert m and k, "sweep summary not found"
    keys = ["inputs", "request", "response", "headers", "agree", "agree_pct", "disagree"]
    out = dict(zip(keys, m.groups()))
    out.update(zip(["c_vs_rust", "unexplained", "early_reject"], k.groups()))
    return out


def sweep_features() -> list[list[str]]:
    t = SWEEP.read_text(encoding="utf-8")
    block = t.split("Disagreements by attributed feature.")[1]
    rows = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in block.splitlines() if ln.startswith("| ") and "---" not in ln]
    return rows[1:]  # drop the header row


def sweep_table() -> str:
    n = sweep_numbers()
    f = lambda x: f"{int(x):,}"  # noqa: E731
    rows = "".join(
        f'<tr><th scope="row"><code>{esc(r[0])}</code></th><td class="num">{f(r[1])}</td><td class="num">{f(r[2])}</td><td>{esc(r[3])}</td></tr>'
        for r in sweep_features())
    return (
        f'<p class="prose">Sweep of {f(n["inputs"])} deterministic inputs ({f(n["request"])} request, {f(n["response"])} response, {f(n["headers"])} header block; '
        f'half from the corpus, half from the well-formed generators, two thirds then mutated). All three parsers did the same thing on {f(n["agree"])} ({n["agree_pct"]}%) and disagreed on '
        f'<b>{f(n["disagree"])}</b>. picohttpparser and fuzzdiff differed on <b>{f(n["c_vs_rust"])}</b>; disagreements that no documented class explains: <b>{f(n["unexplained"])}</b>; '
        f'{f(n["early_reject"])} are only httparse rejecting an invalid prefix earlier than the other two. The share is large because the mutator produces folds, doubled spaces and version digits constantly, not because the parsers disagree on typical traffic.</p>'
        '<div class="scroll wide"><table class="tbl bt fz-sweep"><caption>Disagreements by attributed feature, as in docs/DIFFERENTIAL_HTTPARSE.md. Patterns are picohttpparser, fuzzdiff, httparse: C complete, P partial, R reject, ! all complete but fields differ</caption>'
        '<thead><tr><th scope="col">Feature</th><th scope="col" class="num">Inputs attributed</th><th scope="col" class="num">Alone</th><th scope="col">Patterns (count)</th></tr></thead><tbody>'
        + rows + "</tbody></table></div>")
