#!/usr/bin/env python3
"""Capture or verify the real parser results shown by the "Side-by-side parser" bench on the fuzzdiff page.

  python scripts/capture_fuzzdiff_bench.py [--work DIR]            # clone, run, write the data
  python scripts/capture_fuzzdiff_bench.py [--work DIR] --check    # clone, run, compare, change nothing

What it does:
  1. Clones https://github.com/samiali38183/fuzzdiff into DIR/fuzzdiff (default: a scratch directory under the system
     temp folder; an existing clone there is reused) and checks out the tag v0.2.0. It refuses to continue if the
     commit is not the one recorded below. The public repository is never modified; the program below is added only to
     the scratch clone.
  2. Copies scripts/fuzzdiff_bench_capture.rs into the clone as harness/examples/bench_capture.rs and runs
       cargo run --release -p fuzzdiff-harness --features mutants --example bench_capture
     Needs a Rust toolchain and a C compiler (the harness builds picohttpparser with the `cc` crate). The program uses
     only the harness crate's public API: it runs each curated input through picohttpparser (C), fuzzdiff (Rust) and
     httparse 1.10.1, classifies it with the harness's compare_case(), and times the seeded-bug detection loop.
  3. Writes assets/data/fuzzdiff-bench.json (inputs, results, seeded-bug table, control run) and copies the generated
     "curated" and "sweep" tables out of docs/DIFFERENTIAL_HTTPARSE.md to assets/data/fuzzdiff-bench/curated-table.md
     and sweep-table.md (the page renders the sweep table from that copy), so that
     scripts/test_bench_fuzzdiff.mjs can check the bench against the document without a clone.

Nothing in the data is edited by hand. Detection counts and results are deterministic; the *_seconds fields are
wall-clock times on the machine that ran the capture, and --check does not compare them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "fuzzdiff-bench.json"
DOC_OUT = ROOT / "assets" / "data" / "fuzzdiff-bench" / "curated-table.md"
SWEEP_OUT = ROOT / "assets" / "data" / "fuzzdiff-bench" / "sweep-table.md"
PROGRAM = ROOT / "scripts" / "fuzzdiff_bench_capture.rs"

REPO = "https://github.com/samiali38183/fuzzdiff"
TAG = "v0.2.0"
COMMIT = "6ec1e6e96bbcb18dce42421de2c429e53ff38f29"


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.exit(f"command failed: {' '.join(cmd)}\n{p.stderr[-3000:]}")
    return p.stdout


def strip_times(o):
    if isinstance(o, dict):
        return {k: strip_times(v) for k, v in o.items() if not k.endswith("seconds") and k not in ("captured", "rustc")}
    if isinstance(o, list):
        return [strip_times(x) for x in o]
    return o


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "fuzzdiff-bench-work")
    ap.add_argument("--check", action="store_true", help="compare with the stored data instead of writing it")
    a = ap.parse_args()
    a.work = a.work.resolve()

    a.work.mkdir(parents=True, exist_ok=True)
    clone = a.work / "fuzzdiff"
    if not clone.exists():
        run(["git", "clone", "-q", REPO, "fuzzdiff"], a.work)
    run(["git", "fetch", "-q", "--tags"], clone)
    run(["git", "checkout", "-q", TAG], clone)
    sha = run(["git", "rev-parse", "HEAD"], clone).strip()
    if sha != COMMIT:
        sys.exit(f"tag {TAG} is {sha}, expected {COMMIT}")

    ex = clone / "harness" / "examples" / "bench_capture.rs"
    shutil.copyfile(PROGRAM, ex)
    env = dict(os.environ, BENCH_ROOT=str(clone), BENCH_COMMIT=sha[:7], BENCH_DATE=date.today().isoformat(),
               BENCH_RUSTC=run(["rustc", "--version"], clone).strip().split(" (")[0])
    cargo = ["cargo", "run", "--release", "-q", "-p", "fuzzdiff-harness", "--features", "mutants", "--example", "bench_capture"]
    data = json.loads(run(cargo, clone, env))
    ex.unlink()
    run(["git", "checkout", "-q", "--", "."], clone)

    doc = (clone / "docs" / "DIFFERENTIAL_HTTPARSE.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- BEGIN GENERATED: curated -->\n(.*?)<!-- END GENERATED: curated -->", doc, re.S)
    if not m:
        sys.exit("curated table not found in DIFFERENTIAL_HTTPARSE.md")
    table = m.group(1).strip() + "\n"
    ms = re.search(r"<!-- BEGIN GENERATED: sweep -->\n(.*?)<!-- END GENERATED: sweep -->", doc, re.S)
    if not ms:
        sys.exit("sweep table not found in DIFFERENTIAL_HTTPARSE.md")
    sweep = ms.group(1).strip() + "\n"

    # the harness's own expected pattern for each curated input must be the one in the document; the document's
    # "Stricter" column is copied into the data
    rows = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in table.splitlines() if ln.startswith("| ") and "---" not in ln]
    for i in data["inputs"]:
        d = i["doc"]
        if not d:
            continue
        hit = [r for r in rows if r[0] == d["class"] and r[1].endswith("(" + d["label"] + ")")]
        if len(hit) != 1:
            sys.exit(f"{i['id']}: expected one row for '{d['label']}' in the document table, found {len(hit)}")
        r = hit[0]
        if r[5] != d["pattern"] or i["pattern"] != d["pattern"]:
            sys.exit(f"{i['id']}: pattern in the document {r[5]}, harness expectation {d['pattern']}, observed {i['pattern']}")
        d["stricter"] = r[6]

    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if a.check:
        old = json.loads(OUT.read_text(encoding="utf-8"))
        same = strip_times(old) == strip_times(data) and DOC_OUT.read_text(encoding="utf-8").replace("\r\n", "\n") == table and SWEEP_OUT.read_text(encoding="utf-8").replace("\r\n", "\n") == sweep
        print("OK: stored bench data equals a fresh run" if same else "DIFFERENT: stored bench data does not equal a fresh run")
        return 0 if same else 1
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    DOC_OUT.write_text(table, encoding="utf-8", newline="\n")
    SWEEP_OUT.write_text(sweep, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(data['inputs'])} inputs, {len(data['mutants'])} seeded bugs) and {DOC_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
