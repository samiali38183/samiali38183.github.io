#!/usr/bin/env python3
"""Generate the data for the kev-risk-prioritization "Weight bench" from a clone of the real tool.

Usage: python scripts/gen_bench_kev.py --repo PATH_TO_KEV_RISK_CLONE [--check]

Writes (or with --check compares):
  assets/data/bench-kev-risk.json     the 20 findings, presets and provenance (loaded by the live bench)
  assets/data/kev-bench-parity.json   ground truth from kev_prioritize.score_all for the presets and
                                      random weight vectors (test data, not loaded by the page)
  assets/data/kev-snapshot.json       compact figures from the pinned real snapshot (used at build time)
The ranking and scores are never computed here by a re-implementation: they come from the tool itself.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import subprocess
import sys
from bisect import bisect_left
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "assets" / "data"
PRESETS = [("default", "Default weights", (0.40, 0.25, 0.20, 0.20)), ("cvss", "CVSS only", (0, 0, 0, 1)),
           ("epss", "EPSS only", (0, 0, 1, 0)), ("acr", "ACR only", (0, 1, 0, 0))]
N_RANDOM = 300
TOP = 12


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "scripts"))
    import kev_prioritize as kp  # noqa: E402
    import analyze_snapshot as an  # noqa: E402

    tag_commit = git(repo, "rev-list", "-n1", "v0.3.0")
    assert git(repo, "rev-parse", "HEAD") == tag_commit, "clone is not at tag v0.3.0"
    assert kp.__version__ == "0.3.0"
    assert kp.DEFAULT_WEIGHTS == {"kev": 0.40, "acr": 0.25, "epss": 0.20, "cvss": 0.20}

    csv_path, kev_path = repo / "data/sample_findings.csv", repo / "data/sample_kev.json"
    kev = kp.load_kev(str(kev_path))
    base = kp.load_findings(str(csv_path))  # CSV order
    assert len(base) == 20
    # The tool's sort is a total order (score, KEV, EPSS, CVSS, ACR, days open, CVE, asset, group, vendor, exposure).
    # The bench carries the first seven keys and the asset; that is the whole order only if (CVE, asset) is unique,
    # the strings are ASCII (Python compares code points, JavaScript UTF-16 units) and every row has CVSS.
    assert len({(f.cve, f.asset) for f in base}) == 20 and all(f.cve.isascii() and f.asset.isascii() for f in base)
    assert all(f.cvss is not None for f in base) and all(f.cve == f.cve.strip().upper() for f in base)
    # the printed CLI output for the default weights
    cli = subprocess.run([sys.executable, str(repo / "kev_prioritize.py"), str(csv_path), "--kev", str(kev_path), "--top", "20"],
                         capture_output=True, text=True, check=True, cwd=repo).stdout.splitlines()
    cli_rows = cli[1:21]

    def ranked(w: tuple) -> list[tuple[int, float]]:
        fs = copy.deepcopy(base)
        index = {id(f): i for i, f in enumerate(fs)}  # carry the CSV index through the tool's own sort
        weights = dict(zip(("kev", "acr", "epss", "cvss"), w))
        out = kp.score_all(fs, kev, weights)
        return [(index[id(f)], f.risk_score) for f in out]

    cases = []
    for key, _label, w in PRESETS:
        r = ranked(w)
        cases.append({"g": key, "w": list(w), "o": [i for i, _ in r], "s": [s for _, s in r]})
    d = cases[0]
    for pos, ln in enumerate(cli_rows):
        f = base[d["o"][pos]]
        assert f.cve in ln and ("%5.1f" % d["s"][pos]) in ln, (ln, f.cve)

    rng = random.Random(20261111)
    for n in range(N_RANDOM):
        mode = n % 5
        if mode == 0:    # slider grid, step 0.05
            w = tuple(rng.randrange(0, 21) / 20 for _ in range(4))
        elif mode == 1:  # two decimals
            w = tuple(rng.randrange(0, 101) / 100 for _ in range(4))
        elif mode == 2:  # full-precision floats
            w = tuple(rng.random() for _ in range(4))
        elif mode == 3:  # sparse: some weights exactly zero
            w = tuple(rng.choice([0, rng.random()]) for _ in range(4))
        else:            # one dominant weight
            w = tuple(rng.random() * 0.05 for _ in range(4))
            k = rng.randrange(4)
            w = tuple(1.0 if i == k else x for i, x in enumerate(w))
        if sum(w) == 0:
            w = (0.4, 0.25, 0.2, 0.2)
        r = ranked(w)
        cases.append({"g": "random", "w": list(w), "o": [i for i, _ in r], "s": [s for _, s in r]})

    findings = [[f.cve, f.asset, f.acr, f.cvss, f.epss, f.days_open, int(f.cve in kev)] for f in base]
    assert sum(r[6] for r in findings) == 12
    by = {c["g"]: sum(findings[i][6] for i in c["o"][:TOP]) for c in cases[:4]}
    meta = {
        "tool": "kev-risk-prioritization", "version": kp.__version__, "tag": "v0.3.0", "commit": tag_commit[:7],
        "python": sys.version.split()[0], "date": "2026-11-11",
        "command": "python kev_prioritize.py data/sample_findings.csv --kev data/sample_kev.json",
        "parity_cases": len(cases), "random_cases": N_RANDOM, "kev_in_top": by,
    }
    bench = {"meta": meta, "top": TOP, "findings": findings,
             "presets": [{"k": k, "l": lab, "w": list(w)} for k, lab, w in PRESETS]}
    parity = {"meta": meta, "cli_default": cli_rows, "cases": cases}

    subset = an.load_subset()
    kev_e = sorted(r[1] for r in subset if r[3])
    non_e = sorted(r[1] for r in subset if not r[3])
    snap_meta = json.loads((repo / "data/snapshot/SNAPSHOT.json").read_text(encoding="utf-8"))
    pop = snap_meta["population_stats"]
    ths = {}
    for t in ("0.1", "0.5", "0.9"):
        tv = float(t)
        k = sum(1 for e in kev_e if e >= tv)
        s = sum(1 for e in non_e if e >= tv)
        p = pop[t]
        assert k == p["kev_ge"], (t, k, p)
        ths[t] = {"kev": k, "kev_pct": round(100 * k / len(kev_e), 1), "sample": s, "sample_pct": round(100 * s / len(non_e), 2),
                  "pop_non_kev": p["non_kev_ge"], "precision_pct": round(100 * k / (k + p["non_kev_ge"]), 1)}
    lo, hi = an.bootstrap_ci(kev_e, non_e)
    xs = [round(10 ** (-3 + i * 3 / 60), 6) for i in range(61)]

    def ccdf(arr: list[float]) -> list[float]:  # share of the group with EPSS >= x
        return [round(1 - bisect_left(arr, x) / len(arr), 4) for x in xs]

    snap = {
        "meta": {"kev_catalog": snap_meta["kev"]["catalogVersion"], "kev_count": snap_meta["kev"]["count"],
                 "epss_date": snap_meta["epss"]["score_date"][:10], "epss_model": snap_meta["epss"]["model_version"],
                 "epss_total": snap_meta["epss"]["rows_total"], "rows": snap_meta["subset"]["rows"],
                 "kev_rows": len(kev_e), "non_kev_rows": len(non_e), "non_kev_population": snap_meta["subset"]["non_kev_population"],
                 "source": "data/snapshot/epss_subset.csv and SNAPSHOT.json at tag v0.3.0, commit " + tag_commit[:7]},
        "auc": round(an.auc(kev_e, non_e), 4), "auc_lo": round(lo, 4), "auc_hi": round(hi, 4),
        "median": {"kev": round(an.quantile(kev_e, .5), 3), "non_kev": round(an.quantile(non_e, .5), 3)},
        "thresholds": ths, "x": xs, "kev": ccdf(kev_e), "non_kev": ccdf(non_e),
    }

    files = {"bench-kev-risk.json": bench, "kev-bench-parity.json": parity, "kev-snapshot.json": snap}
    bad = 0
    for name, obj in files.items():
        text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n"
        p = OUT / name
        if a.check:
            same = p.exists() and p.read_text(encoding="utf-8") == text
            print(("same " if same else "DIFFERENT ") + name)
            bad += not same
        else:
            p.write_text(text, encoding="utf-8", newline="\n")
            print("wrote", name, len(text), "bytes")
    print("KEV in top 12:", by, "| AUC", snap["auc"], snap["auc_lo"], snap["auc_hi"], "| median", snap["median"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
