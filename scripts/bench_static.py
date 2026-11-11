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
