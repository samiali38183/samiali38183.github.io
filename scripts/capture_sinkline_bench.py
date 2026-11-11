#!/usr/bin/env python3
"""Capture or verify the real `sinkline scan` outputs shown by the Sanitizer switch bench.

  python scripts/capture_sinkline_bench.py --sinkline PATH_TO_SINKLINE            # run the CLI, write captures
  python scripts/capture_sinkline_bench.py --sinkline PATH_TO_SINKLINE --check    # run the CLI, compare, change nothing

Inputs are the small Flask files in assets/data/sinkline-bench/*.py. For each one the script runs
`sinkline scan --no-color --fail-on low FILE` (text) and `sinkline scan --no-color -f json FILE` (structure) from
inside that directory, and writes:

  assets/data/sinkline-bench/FILE.txt        stdout of the text run, byte for byte (newlines normalized to LF)
  assets/data/bench-sinkline.json            provenance, the sources, the captured stdout and exit status, and the
                                             findings (rule, CWE, severity, confidence, fix, route) read from the JSON run

Nothing is edited by hand and nothing is analysed here: the script only runs the tool and records what it printed.
--check exits 1 if any stored capture, source file or the JSON differs from a fresh run (the tool version, the
captured date and the Python version are provenance and are not compared except the version of sinkline).
"""
from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "assets" / "data" / "sinkline-bench"
OUT = ROOT / "assets" / "data" / "bench-sinkline.json"

TOOL_VERSION = "0.5.0"
TOOL_COMMIT = "9c58efd"          # tag v0.5.0
CAPTURED = "2026-11-11"

# Variants of one example share a route and differ by one line (or, for the wrong-class XSS case, two).
EXAMPLES = [
    {
        "id": "sql",
        "title": "SQL injection",
        "cwe": "CWE-89",
        "variants": [
            ("unsafe", "Unsafe", "sql-unsafe.py"),
            ("right", "Right-class sanitizer", "sql-right.py"),
            ("wrong", "Wrong-class sanitizer", "sql-wrong.py"),
        ],
    },
    {
        "id": "cmd",
        "title": "Command injection",
        "cwe": "CWE-78",
        "variants": [
            ("unsafe", "Unsafe", "cmd-unsafe.py"),
            ("right", "Right-class sanitizer", "cmd-right.py"),
            ("wrong", "Wrong-class sanitizer", "cmd-wrong.py"),
        ],
    },
    {
        "id": "html",
        "title": "Cross-site scripting",
        "cwe": "CWE-79",
        "variants": [
            ("unsafe", "Unsafe", "html-unsafe.py"),
            ("right", "Right-class sanitizer", "html-right.py"),
            ("wrong", "Wrong-class sanitizer", "html-wrong.py"),
        ],
    },
]
# Captured and compared like the rest, shown only in the page's limits.
EXTRA = [("html-wrong-direct", "html-wrong-direct.py")]


def sinkline_cmd(arg: str | None) -> list[str]:
    if arg:
        return [arg]
    found = shutil.which("sinkline")
    return [found] if found else [sys.executable, "-m", "sinkline"]


def run(base: list[str], args: list[str]) -> tuple[str, int]:
    p = subprocess.run(base + args, cwd=DIR, capture_output=True, check=False)
    if p.stderr.strip():
        raise SystemExit(f"sinkline wrote to stderr: {p.stderr.decode('utf-8', 'replace')}")
    return p.stdout.decode("utf-8").replace("\r\n", "\n"), p.returncode


def capture_one(base: list[str], fname: str) -> dict:
    code = (DIR / fname).read_text(encoding="utf-8").replace("\r\n", "\n")
    text, status = run(base, ["scan", "--no-color", "--fail-on", "low", fname])
    raw, status_json = run(base, ["scan", "--no-color", "-f", "json", fname])
    data = json.loads(raw)
    findings = []
    for f in data["findings"]:
        findings.append({
            "rule_id": f["rule_id"], "cwe": f["cwe"], "severity": f["severity"], "confidence": f["confidence"],
            "title": f["title"], "line": f["line"], "fix": f["fix"],
            "route": [{"kind": s["kind"], "line": s["line"], "note": s["note"]} for s in f["flow"]],
        })
    return {"file": fname, "code": code, "status": status, "out": text, "findings": findings, "errors": data["errors"]}


def changed_lines(base_code: str, code: str) -> list[int]:
    """1-based lines of `code` that are not in `base_code` (plain difflib; display only)."""
    a, b = base_code.splitlines(), code.splitlines()
    out: list[int] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(range(j1 + 1, j2 + 1))
    return out


def tool_version(base: list[str]) -> str:
    out, _ = run(base, ["--version"])
    return out.strip()


def build(base: list[str]) -> dict:
    version = tool_version(base)
    if version != f"sinkline {TOOL_VERSION}":
        raise SystemExit(f"expected 'sinkline {TOOL_VERSION}', got {version!r}")
    examples = []
    for ex in EXAMPLES:
        caps = {vid: capture_one(base, fname) for vid, _label, fname in ex["variants"]}
        base_code = caps["unsafe"]["code"]
        variants = []
        for vid, label, _fname in ex["variants"]:
            c = caps[vid]
            c.update({"id": vid, "label": label, "changed": [] if vid == "unsafe" else changed_lines(base_code, c["code"])})
            variants.append(c)
        examples.append({"id": ex["id"], "title": ex["title"], "cwe": ex["cwe"], "variants": variants})
    extra = [capture_one(base, fname) for _id, fname in EXTRA]
    return {
        "provenance": {
            "tool": "sinkline", "version": TOOL_VERSION, "commit": TOOL_COMMIT, "captured": CAPTURED,
            "command": "sinkline scan --no-color --fail-on low FILE", "cwd": "assets/data/sinkline-bench",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "examples": examples,
        "extra": extra,
    }


def txt_name(fname: str) -> str:
    return fname[:-3] + ".txt"


def comparable(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    d["provenance"].pop("python", None)
    d["provenance"].pop("captured", None)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sinkline", help="path to the sinkline executable (default: PATH, then python -m sinkline)")
    ap.add_argument("--check", action="store_true", help="compare with the stored captures, write nothing")
    a = ap.parse_args()
    base = sinkline_cmd(a.sinkline)
    fresh = build(base)
    files = [v["file"] for ex in fresh["examples"] for v in ex["variants"]] + [e["file"] for e in fresh["extra"]]
    all_caps = [v for ex in fresh["examples"] for v in ex["variants"]] + fresh["extra"]

    if not a.check:
        for c in all_caps:
            (DIR / txt_name(c["file"])).write_text(c["out"], encoding="utf-8", newline="\n")
        OUT.write_text(json.dumps(fresh, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {len(all_caps)} captures and {OUT.relative_to(ROOT)} (sinkline {TOOL_VERSION})")
        return 0

    problems: list[str] = []
    for c in all_caps:
        p = DIR / txt_name(c["file"])
        if not p.exists():
            problems.append(f"missing {p.name}")
        elif p.read_text(encoding="utf-8") != c["out"]:
            problems.append(f"{p.name} differs from a fresh run")
    if not OUT.exists():
        problems.append(f"missing {OUT.name}")
    else:
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(fresh):
            problems.append(f"{OUT.name} differs from a fresh run")
    stray = sorted(p.name for p in DIR.glob("*.txt") if p.name not in {txt_name(f) for f in files})
    stray += sorted(p.name for p in DIR.glob("*.py") if p.name not in set(files))
    if stray:
        problems.append("unlisted files: " + ", ".join(stray))
    for line in problems:
        print("FAIL", line)
    print(f"checked {len(all_caps)} captures against sinkline {TOOL_VERSION}: {'OK' if not problems else 'FAILED'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
