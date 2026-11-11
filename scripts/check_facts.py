#!/usr/bin/env python3
"""Re-derive the numbers shown on the site from their sources and compare them with the HTML.

Usage:
  python scripts/check_facts.py --clones DIR [--venv tripline=PATH ...] [--go GOBIN]

DIR holds fresh clones named tripline, sinkline, kevgate, kevgate-admit and kev-risk-prioritization.
--venv gives the virtualenv directory (with the project installed with its dev extras) for a Python
project; without it the current interpreter is used. Needs git, the gh CLI (authenticated) and Go.
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
results: list[tuple[bool, str]] = []


def text_of(page: str) -> str:
    html = (SITE / page).read_text(encoding="utf-8")
    html = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&amp;", "&")


def expect(label: str, derived: str, page: str, needle: str | None = None) -> None:
    """Check that `needle` (default: derived) appears in the page text."""
    needle = needle or derived
    ok = needle in text_of(page)
    results.append((ok, f"{label}: source says {derived!r}; page {page} {'contains' if ok else 'is MISSING'} {needle!r}"))


def run(cmd: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout + p.stderr


def gh(path: str) -> dict | list:
    return json.loads(run(["gh", "api", path]))


def pybin(venvs: dict[str, str], name: str, exe: str) -> str:
    if name in venvs:
        sub = "Scripts" if os.name == "nt" else "bin"
        return str(Path(venvs[name]) / sub / (exe + (".exe" if os.name == "nt" and exe != "python" else "")))
    return exe if exe != "python" else sys.executable


def collected(py: str, repo: Path) -> int:
    out = run([py, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], repo)
    m = re.search(r"(\d+) tests? collected", out)
    if m:
        return int(m.group(1))
    return sum(int(x) for x in re.findall(r": (\d+)$", out, re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clones", required=True)
    ap.add_argument("--venv", action="append", default=[])
    ap.add_argument("--go", default="go")
    a = ap.parse_args()
    clones = Path(a.clones)
    venvs = dict(v.split("=", 1) for v in a.venv)

    # Release tags from the GitHub API.
    for repo, page in [("tripline", "projects/tripline/index.html"), ("sinkline", "projects/sinkline/index.html"),
                       ("kevgate", "projects/kevgate/index.html")]:
        tag = gh(f"repos/samiali38183/{repo}/releases/latest")["tag_name"]
        expect(f"{repo} latest release", tag, page)
        expect(f"{repo} latest release on home", tag, "index.html")

    # tripline
    t = clones / "tripline"
    sc = json.loads((t / "docs" / "scorecard.json").read_text(encoding="utf-8"))["totals"]
    expect("tripline gate", f"{sc['passed']} passed, {sc['failed']} failed, {sc['pending']} pending", "projects/tripline/index.html")
    expect("tripline scenarios", str(sc["scenarios"]), "projects/tripline/index.html", f"{sc['scenarios']} scenarios")
    pct = round(sc["weighted_coverage"] * 100)
    expect("tripline weighted coverage", f"{pct}%", "projects/tripline/index.html")
    out = run([pybin(venvs, "tripline", "tripline"), "replay", "--all"], t)
    ps = len(re.findall(r"^\[\s+PASS\]", out, re.M))
    pe = len(re.findall(r"^\[PENDING\]", out, re.M))
    results.append((ps == sc["passed"] and pe == sc["pending"] and "gate passed" in out,
                    f"tripline replay --all output: {ps} PASS, {pe} PENDING, gate passed={'gate passed' in out}"))
    n = collected(pybin(venvs, "tripline", "python"), t)
    expect("tripline tests (pytest collection)", str(n), "projects/tripline/index.html", f"{n} (89%")
    expect("tripline tests on resume page", str(n), "resume/index.html", f"{n} tests")
    code = (
        "from pathlib import Path\n"
        "from tripline.engine.rules import load_rules, evaluate\n"
        "from tripline.replay import load_fixture_events\n"
        "from tripline.scenarios import load_scenarios\n"
        "root=Path('.')\n"
        "sc={s.id:s for s in load_scenarios(root/'scenarios')}['t1548-001-setuid-setgid']\n"
        "ev=load_fixture_events(sc,root)\n"
        "rs={r.id:r for r in load_rules(root/'rules'/'sigma').rules}\n"
        "for rid in ('c21c4eaa-ba2e-419a-92b2-8371703cbe21','7f3c2b1a-6d4e-4a9b-9c8d-1e2f3a4b5c6d'):\n"
        "    res=[evaluate(rs[rid],e) for e in ev]\n"
        "    print(sum(x is not None for x in res), sum(x is True for x in res))\n"
    )
    o = run([pybin(venvs, "tripline", "python"), "-c", code], t).split()
    if len(o) == 4:
        expect("tripline stock rule hits", f"{o[1]} of {o[0]}", "projects/tripline/index.html")
        expect("tripline replacement rule hits", f"{o[3]} of {o[2]}", "projects/tripline/index.html")
    else:
        results.append((False, f"tripline F-001 derivation failed: {o}"))

    # sinkline
    s = clones / "sinkline"
    py = pybin(venvs, "sinkline", "python")
    sco = run([py, "bench/score.py"], s)
    m = re.search(r"TP (\d+)\s+FP (\d+)\s+FN (\d+)\s+TN (\d+)\s+precision ([\d.]+)\s+recall ([\d.]+)\s+F1 ([\d.]+)", sco)
    if m:
        tp, fp, fn, tn, p_, r_, f1 = m.groups()
        expect("sinkline benchmark counts", f"TP {tp}, FP {fp}, FN {fn}, TN {tn}", "projects/sinkline/index.html")
        expect("sinkline benchmark P/R/F1", f"{p_} {r_} {f1}", "projects/sinkline/index.html", f"P {p_}, R {r_}, F1 {f1}")
        expect("sinkline F1 on home", f1, "index.html", f"F1 {f1}")
        lab = re.search(r"corpus: (\d+) labeled lines", sco)
        expect("sinkline corpus size", lab.group(1), "projects/sinkline/index.html", f"{lab.group(1)} lines")
    else:
        results.append((False, "sinkline bench/score.py output not parsed"))
    cb = run([py, "bench/compare_bandit.py"], s)
    m = re.search(r"TP (\d+)\s+FP (\d+)\s+FN (\d+)\s+TN (\d+)\s+precision ([\d.]+)\s+recall ([\d.]+)\s+F1 ([\d.]+)", cb)
    if m:
        tp, fp, fn, tn, p_, r_, f1 = m.groups()
        expect("bandit benchmark", f"TP {tp}, FP {fp}, FN {fn}, TN {tn}", "projects/sinkline/index.html")
        expect("bandit F1 on home", f1, "index.html", f"F1 of {f1}")
    else:
        results.append((False, "sinkline compare_bandit output not parsed"))
    n = collected(py, s)
    expect("sinkline tests", str(n), "projects/sinkline/index.html", f"{n} (includes")
    rules = run([pybin(venvs, "sinkline", "sinkline"), "rules"], s)
    m = re.search(r"(\d+) rules, (\d+) sink signatures", rules)
    if m:
        expect("sinkline rules and sinks", m.group(0), "projects/sinkline/index.html", f"{m.group(1)} rules, {m.group(2)} sink signatures")

    # kevgate
    k = clones / "kevgate"
    n = collected(pybin(venvs, "kevgate", "python"), k)
    expect("kevgate tests (main)", str(n), "projects/kevgate/index.html", f"{n} collected")
    expect("kevgate tests on home", str(n), "index.html", f"{n} tests")
    tagsha = run(["git", "rev-list", "-n1", "v0.1.0"], k).strip()[:7]
    expect("kevgate v0.1.0 tag commit", tagsha, "projects/kevgate/index.html")
    for wf in ("ci", "security", "deploy-kind", "terraform", "release"):
        pass
    html = (SITE / "projects/kevgate/index.html").read_text(encoding="utf-8")
    html_admit = (SITE / "projects/kevgate-admit/index.html").read_text(encoding="utf-8")
    all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
    for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/([\w.-]+)/actions/runs/(\d+)", all_html))):
        r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
        # The two tripline emulation runs are red by design: their last step asserts that expected rules fire.
        expected_red = rid in {"41838714456", "42917025570"}
        results.append((r.get("conclusion") == ("failure" if expected_red else "success"),
                        f"CI run {repo}/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')}{' (expected red, linked as the recording source)' if expected_red else ''} sha={r.get('head_sha', '')[:7]}"))

    # kev-risk-prioritization
    kr = clones / "kev-risk-prioritization"
    out = run([pybin(venvs, "kev", "python"), "kev_prioritize.py", "data/sample_findings.csv", "--kev", "data/sample_kev.json", "--format", "json"], kr)
    data = json.loads(out)
    ranked = data["ranked"]
    kev_n = sum(1 for x in ranked if x["kev"])
    top12_cvss = sorted(ranked, key=lambda x: -x["cvss"])[:12]
    # the repo's CVSS-only sort breaks ties by input order; this uses the same stable sort
    rows = list(csv.DictReader((kr / "data" / "sample_findings.csv").open(encoding="utf-8")))
    kevset = {x["cve"] for x in ranked if x["kev"]}
    cvss_top = sorted(rows, key=lambda x: -float(x["cvss"]))[:12]
    nk = sum(1 for x in cvss_top if x["cve"].upper() in kevset)
    expect("kev-risk sample (KEV of total)", f"{kev_n} of {len(ranked)}", "projects/kev-risk-prioritization/index.html", f"n={kev_n}")
    expect("kev-risk CVSS-only top 12 KEV count", str(nk), "projects/kev-risk-prioritization/index.html", f"{nk} KEV findings in its top 12")
    expect("kev-risk top risk score", str(ranked[0]["risk_score"]), "projects/kev-risk-prioritization/index.html")
    n = collected(pybin(venvs, "kev", "python"), kr)
    expect("kev-risk tests", str(n), "projects/kev-risk-prioritization/index.html", f"{n} tests pass")

    # kevgate-admit (Go)
    ka = clones / "kevgate-admit"
    env_go = a.go
    pj = run([env_go, "test", "./...", "-json"], ka)
    top, allt = set(), set()
    for line in pj.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") == "pass" and e.get("Test"):
            allt.add((e["Package"], e["Test"]))
            if "/" not in e["Test"]:
                top.add((e["Package"], e["Test"]))
    expect("kevgate-admit top-level tests", str(len(top)), "projects/kevgate-admit/index.html", f"{len(top)} top-level")
    expect("kevgate-admit all tests", str(len(allt)), "projects/kevgate-admit/index.html", f"{len(allt)} with subtests")
    run([env_go, "test", "./...", "-coverprofile=c.out"], ka)
    cov = run([env_go, "tool", "cover", "-func=c.out"], ka).strip().splitlines()[-1]
    m = re.search(r"([\d.]+)%", cov)
    expect("kevgate-admit coverage", m.group(1) + "%", "projects/kevgate-admit/index.html")
    vec = json.loads((ka / "internal" / "risk" / "testdata" / "parity_vectors.json").read_text(encoding="utf-8"))
    expect("kevgate-admit parity vectors", str(len(vec)), "projects/kevgate-admit/index.html", f"{len(vec)} reference vectors")
    try:
        (ka / "c.out").unlink()
    except OSError:
        pass

    bad = 0
    for ok, msg in results:
        print(("PASS  " if ok else "FAIL  ") + msg)
        bad += not ok
    print(f"\n{len(results) - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
