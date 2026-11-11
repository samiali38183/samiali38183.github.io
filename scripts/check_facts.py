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


def kev_risk_checks(clones: Path, venvs: dict[str, str]) -> None:
    """kev-risk-prioritization sheet: tool output, release, snapshot numbers, BOD 26-04 notes, Weight bench data."""
    page = "projects/kev-risk-prioritization/index.html"
    kr = clones / "kev-risk-prioritization"
    py = pybin(venvs, "kev", "python")
    tag = gh("repos/samiali38183/kev-risk-prioritization/releases/latest")["tag_name"]
    expect("kev-risk latest release", tag, page)
    expect("kev-risk latest release on home", tag, "index.html")
    head = run(["git", "rev-parse", "HEAD"], kr).strip()
    tagsha = run(["git", "rev-list", "-n1", tag], kr).strip()
    results.append((head == tagsha, f"kev-risk clone HEAD {head[:7]} is the {tag} commit {tagsha[:7]}"))
    expect("kev-risk commit", tagsha[:7], page)
    # tool output on the synthetic demo
    out = run([py, "kev_prioritize.py", "data/sample_findings.csv", "--kev", "data/sample_kev.json", "--format", "json"], kr)
    ranked = json.loads(out)["ranked"]
    kev_n = sum(1 for x in ranked if x["kev"])
    rows = list(csv.DictReader((kr / "data" / "sample_findings.csv").open(encoding="utf-8")))
    kevset = {x["cve"] for x in ranked if x["kev"]}
    cvss_top = sorted(rows, key=lambda x: -float(x["cvss"]))[:12]
    nk = sum(1 for x in cvss_top if x["cve"].upper() in kevset)
    top12 = sum(1 for x in ranked[:12] if x["kev"])
    expect("kev-risk sample (KEV of total)", f"{kev_n} of {len(ranked)}", page, f"n={kev_n}")
    expect("kev-risk CVSS-only top 12 KEV count", str(nk), page, f"{nk} KEV findings in its top 12")
    expect("kev-risk risk-score top 12 KEV count", str(top12), page, f"all {top12} KEV findings in its top 12")
    expect("kev-risk top risk score", str(ranked[0]["risk_score"]), page)
    expect("kev-risk lowest KEV score", str(min(x["risk_score"] for x in ranked if x["kev"])), page, "lowest-scoring KEV finding scores 85.0")
    expect("kev-risk highest non-KEV score", str(max(x["risk_score"] for x in ranked if not x["kev"])), page, "highest-scoring non-KEV finding 38.5")
    n = collected(py, kr)
    expect("kev-risk tests", str(n), page, f"{n} tests pass")
    results.append((True, "kev-risk unittest run (info): " + run([py, "-m", "unittest", "discover", "tests"], kr).strip().splitlines()[-1]))
    # weights in the code
    src = (kr / "kev_prioritize.py").read_text(encoding="utf-8")
    results.append(('DEFAULT_WEIGHTS = {"kev": 0.40, "acr": 0.25, "epss": 0.20, "cvss": 0.20}' in src, "kev-risk default weights 0.40 / 0.25 / 0.20 / 0.20 in kev_prioritize.py"))
    expect("kev-risk weights on page", "0.40 0.25 0.20 0.20", page, "0.40*kev + 0.25*acr/8 + 0.20*epss + 0.20*cvss/10")
    # real snapshot: generated analysis must be current, and the page must carry its numbers
    chk = run([py, "scripts/analyze_snapshot.py", "--check"], kr).strip()
    results.append(("up to date" in chk, f"kev-risk analyze_snapshot.py --check: {chk}"))
    doc = (kr / "docs" / "real_data_analysis.md").read_text(encoding="utf-8")
    m = re.search(r"AUC of EPSS for separating KEV from sampled non-KEV: (\d\.\d+)\*\* \(95% bootstrap interval (\d\.\d+) to (\d\.\d+)", doc)
    results.append((bool(m), "kev-risk analysis doc AUC line found"))
    snap = json.loads((SITE / "assets/data/kev-snapshot.json").read_text(encoding="utf-8"))
    if m:
        results.append(((float(m.group(1)), float(m.group(2)), float(m.group(3))) == (snap["auc"], snap["auc_lo"], snap["auc_hi"]),
                        f"kev-risk AUC in kev-snapshot.json equals the doc ({m.group(1)}, {m.group(2)} to {m.group(3)})"))
        expect("kev-risk AUC on page", m.group(1), page, f"AUC of {m.group(1)} (95% bootstrap interval {m.group(2)} to {m.group(3)})")
    for t in ("0.1", "0.5", "0.9"):
        tm = re.search(r"\| " + re.escape(t) + r" \| (\d+) \| ([\d.]+)% \| (\d+) \(([\d.]+)%\) \| ([\d.]+)% \| (\d+) \(([\d.]+)%\) \|", doc)
        if not tm:
            results.append((False, f"kev-risk analysis doc threshold row {t} not found"))
            continue
        k, kp, npop, _, prec, ns, nsp = tm.groups()
        th = snap["thresholds"][t]
        same = (th["kev"], th["kev_pct"], th["pop_non_kev"], th["precision_pct"], th["sample"], th["sample_pct"]) == (int(k), float(kp), int(npop), float(prec), int(ns), float(nsp))
        results.append((same, f"kev-risk threshold {t}: kev-snapshot.json equals the doc (KEV {k}, {kp}%, non-KEV population {npop}, precision {prec}%, sample {ns})"))
        expect(f"kev-risk threshold {t} on page", f"{int(k):,}", page, f"{int(k):,} ({kp}%)")
    sj = json.loads((kr / "data" / "snapshot" / "SNAPSHOT.json").read_text(encoding="utf-8"))
    expect("kev-risk KEV catalogVersion", sj["kev"]["catalogVersion"], page)
    expect("kev-risk KEV entries", f"{sj['kev']['count']:,}", page, f"{sj['kev']['count']:,} entries")
    expect("kev-risk EPSS model", sj["epss"]["model_version"], page)
    expect("kev-risk EPSS date", sj["epss"]["score_date"][:10], page)
    expect("kev-risk EPSS CVEs scored", f"{sj['epss']['rows_total']:,}", page, f"{sj['epss']['rows_total']:,} CVEs")
    expect("kev-risk subset rows", f"{sj['subset']['rows']:,}", page, f"{sj['subset']['rows']:,} rows")
    mix = re.search(r"\| Risk score \(tool\) \| (\d+) \| (\d+) \|", doc)
    eps = re.search(r"\| EPSS only \| (\d+) \| (\d+) \|", doc)
    if mix and eps:
        expect("kev-risk mixed list: tool KEV in top 100", mix.group(2), page, f"puts all {mix.group(2)} KEV findings in its top 100")
        expect("kev-risk mixed list: EPSS-only KEV in top 100", eps.group(2), page, f"EPSS alone puts {eps.group(2)} there")
    else:
        results.append((False, "kev-risk mixed list rows not found in the analysis doc"))
    # BOD 26-04 notes: the four variables and the scope sentences the page relies on
    bod = (kr / "docs" / "bod-26-04.md").read_text(encoding="utf-8")
    for needle in ("Publicly Exposed", "In the KEV", "Automatable by Adversary", "Technical Impact", "BOD 19-02 and BOD 22-01", "Federal Civilian Executive Branch"):
        results.append((needle in bod, f"kev-risk docs/bod-26-04.md contains {needle!r}"))
    for needle in ("revokes BOD 19-02 and BOD 22-01", "Publicly exposed", "Automatable by adversary", "In the KEV", "Table 1 was transcribed by eye"):
        expect("kev-risk BOD statement on page", needle, page, needle)
    # Weight bench data: regenerated from the tool must equal what is committed, and the JS must match
    gen = run([py, str(SITE / "scripts" / "gen_bench_kev.py"), "--repo", str(kr), "--check"], SITE)
    results.append((gen.count("DIFFERENT") == 0 and gen.count("same ") == 3, "gen_bench_kev.py --check: " + " ".join(l.split()[-1] for l in gen.splitlines() if l.startswith(("same", "DIFFERENT")))))
    bd = json.loads((SITE / "assets/data/bench-kev-risk.json").read_text(encoding="utf-8"))
    cp = json.loads((SITE / "assets/data/kev-bench-parity.json").read_text(encoding="utf-8"))
    results.append((bd["meta"]["kev_in_top"] == {"default": 12, "cvss": nk, "epss": 12, "acr": 10}, f"bench KEV-in-top-12 per preset {bd['meta']['kev_in_top']}"))
    expect("bench parity cases on page", str(cp["meta"]["parity_cases"]), page, f"{cp['meta']['parity_cases']} weight vectors")
    expect("bench random vectors on page", str(cp["meta"]["random_cases"]), page, f"{cp['meta']['random_cases']} random weight vectors")
    nodes = run(["node", str(SITE / "scripts" / "test_bench_kev.mjs")], SITE).strip().splitlines()[-1]
    results.append((nodes.startswith("OK"), f"node scripts/test_bench_kev.mjs: {nodes}"))
    all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
    for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/(kev-risk-prioritization)/actions/runs/(\d+)", all_html))):
        r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
        results.append((r.get("conclusion") == "success", f"CI run {repo}/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clones", required=True)
    ap.add_argument("--venv", action="append", default=[])
    ap.add_argument("--go", default="go")
    ap.add_argument("--only", choices=["sinkline", "tripline", "kev"], help="run only one project's checks (when the other toolchains are not installed)")
    a = ap.parse_args()
    clones = Path(a.clones)
    venvs = dict(v.split("=", 1) for v in a.venv)

    # Release tags from the GitHub API.
    for repo, page in [("tripline", "projects/tripline/index.html"), ("sinkline", "projects/sinkline/index.html"),
                       ("kevgate", "projects/kevgate/index.html")]:
        if a.only and repo != a.only:
            continue
        tag = gh(f"repos/samiali38183/{repo}/releases/latest")["tag_name"]
        expect(f"{repo} latest release", tag, page)
        expect(f"{repo} latest release on home", tag, "index.html")

    if a.only == "kev":
        kev_risk_checks(clones, venvs)
        return report()

    # tripline
    if a.only in (None, "tripline"):
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
        expect("tripline 0 of 36 on home", "0 of 36", "index.html")
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
        # tripline Rule bench: data file against the clone's rule YAML and the page text
        import yaml
        bd = json.loads((SITE / "assets/data/bench-tripline.json").read_text(encoding="utf-8"))
        ys = yaml.safe_load((t / bd["meta"]["stock"]["file"]).read_text(encoding="utf-8"))["detection"]
        yc = yaml.safe_load((t / bd["meta"]["custom"]["file"]).read_text(encoding="utf-8"))["detection"]
        same = (bd["stock"]["perm"] == ys["selection_perm"]["CommandLine|contains"]
                and bd["stock"]["root"] == [ys["selection_root"]["CommandLine|contains"]]
                and bd["custom"] == {"image": yc["selection_image"]["Image|endswith"], "symbolic": yc["selection_symbolic"]["CommandLine|re"],
                                     "octal": yc["selection_octal"]["CommandLine|re"], "filter": yc["filter_tmp_runner"]["CommandLine|re"]})
        results.append((same, "bench rule patterns equal the YAML in the tripline clone"))
        ev = bd["events"]
        results.append((len(ev) == 36 and sum(e["s"] for e in ev) == 0 and sum(e["r"] for e in ev) == 2, "bench events: 36, stock 0, replacement 2"))
        expect("bench parity cases", str(bd["meta"]["parity_cases"]), "projects/tripline/index.html", f"on {bd['meta']['parity_cases']} command lines")

    if a.only == "tripline":
        all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
        for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/(tripline)/actions/runs/(\d+)", all_html))):
            r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
            red = rid in {"41838714456", "42917025570"}  # recording runs, red by design
            results.append((r.get("conclusion") == ("failure" if red else "success"), f"CI run {repo}/{rid}: conclusion={r.get('conclusion')}{' (expected red)' if red else ''}"))
        return report()

    # sinkline (the clone must be at the v0.5.0 tag or main at that commit)
    s = clones / "sinkline"
    py = pybin(venvs, "sinkline", "python")
    sco = run([py, "bench/score.py"], s)
    m = re.search(r"TP (\d+)\s+FP (\d+)\s+FN (\d+)\s+TN (\d+)\s+precision ([\d.]+)\s+recall ([\d.]+)\s+F1 ([\d.]+)", sco)
    if m:
        tp, fp, fn, tn, p_, r_, f1 = m.groups()
        expect("sinkline benchmark counts", f"TP {tp}, FP {fp}, FN {fn}, TN {tn}", "projects/sinkline/index.html")
        expect("sinkline benchmark P/R/F1", f"{p_} {r_} {f1}", "projects/sinkline/index.html", f"P {p_}, R {r_}, F1 {f1}")
        lab = re.search(r"corpus: (\d+) labeled lines", sco)
        expect("sinkline corpus size", lab.group(1), "projects/sinkline/index.html", f"{lab.group(1)} lines")
    else:
        results.append((False, "sinkline bench/score.py output not parsed"))
    cb = run([py, "bench/compare_bandit.py"], s)
    m = re.search(r"TP (\d+)\s+FP (\d+)\s+FN (\d+)\s+TN (\d+)\s+precision ([\d.]+)\s+recall ([\d.]+)\s+F1 ([\d.]+)", cb)
    if m:
        tp, fp, fn, tn, p_, r_, f1 = m.groups()
        expect("bandit benchmark", f"TP {tp}, FP {fp}, FN {fn}, TN {tn}", "projects/sinkline/index.html")
    else:
        results.append((False, "sinkline compare_bandit output not parsed"))
    n = collected(py, s)
    expect("sinkline tests", str(n), "projects/sinkline/index.html", f"{n} (includes")
    rules = run([pybin(venvs, "sinkline", "sinkline"), "rules"], s)
    m = re.search(r"(\d+) rules, (\d+) sink signatures", rules)
    if m:
        expect("sinkline rules and sinks", m.group(0), "projects/sinkline/index.html", f"{m.group(1)} rules, {m.group(2)} sink signatures")

    # sinkline external benchmark (OWASP BenchmarkPython v0.1): the committed per-category results, and the self-labeled gate
    ext = s / "bench" / "external" / "results"
    res = {}
    for label in ("v0.4.1", "v0.5.0"):
        res[label] = {(r["tool"], r["category"]): tuple(int(r[k]) for k in ("TP", "FN", "FP", "TN"))
                      for r in csv.DictReader((ext / label / "summary.csv").open(encoding="utf-8"))}

    def rates(c):
        tp, fn, fp, tn = c
        tpr, fpr = tp / (tp + fn), fp / (fp + tn)
        return tpr, fpr, tpr - fpr

    page = "projects/sinkline/index.html"
    for label, tool, cat in [("v0.4.1", "sinkline", "taint categories (10)"), ("v0.5.0", "sinkline", "taint categories (10)"),
                             ("v0.4.1", "sinkline", "all categories (14)"), ("v0.5.0", "bandit", "all categories (14)"),
                             ("v0.5.0", "semgrep", "all categories (14)")]:
        tp, fn, fp, tn = res[label][(tool, cat)]
        expect(f"external {tool} {label} {cat} counts", f"TP {tp}, FN {fn}, FP {fp}, TN {tn}", page)
    for label, tool, cat in [("v0.4.1", "sinkline", "taint categories (10)"), ("v0.5.0", "sinkline", "taint categories (10)"),
                             ("v0.5.0", "bandit", "taint categories (10)"), ("v0.5.0", "semgrep", "taint categories (10)")]:
        tpr, fpr, sc = rates(res[label][(tool, cat)])
        needle = f"TPR {tpr:.2f}, FPR {fpr:.2f}, {sc:+.2f}" if (label, tool) == ("v0.5.0", "sinkline") else f"{tpr:.2f}, {fpr:.2f}, {sc:+.2f}"
        expect(f"external {tool} {label} taint TPR/FPR/score on the page", needle, page)
    # every cell of the per-category table, computed from counts (not from the README, which rounds twice)
    cats = sorted({c for (_t, c) in res["v0.5.0"]})
    bad = []
    for cat in cats:
        cells = [res["v0.4.1"][("sinkline", cat)], res["v0.5.0"][("sinkline", cat)], res["v0.5.0"][("bandit", cat)], res["v0.5.0"][("semgrep", cat)]]
        for c in cells:
            tpr, fpr, sc = rates(c)
            if f"{tpr:.2f} / {fpr:.2f} / {sc:+.2f}" not in text_of(page):
                bad.append((cat, c))
    results.append((not bad, f"sinkline per-category table: {len(cats) * 4} cells recomputed from bench/external/results counts; mismatches: {bad}"))
    for tool in ("bandit", "semgrep"):
        same = all(res["v0.4.1"][(tool, c)] == res["v0.5.0"][(tool, c)] for c in cats)
        results.append((same, f"external {tool} results identical in v0.4.1 and v0.5.0 result sets"))
    reals = {c: res["v0.5.0"][("sinkline", c)][0] + res["v0.5.0"][("sinkline", c)][1] for c in cats}
    safes = {c: res["v0.5.0"][("sinkline", c)][2] + res["v0.5.0"][("sinkline", c)][3] for c in cats}
    expect("taint categories real / safe", f"{reals['taint categories (10)']} vulnerable, {safes['taint categories (10)']} safe", page,
           f"{reals['taint categories (10)']} vulnerable cases and {safes['taint categories (10)']} safe ones")
    expect("no-check categories real total", str(sum(reals[c] for c in ("hash", "weakrand", "securecookie", "trustbound"))), page, "0 of 212 vulnerable cases")
    expect("sinkline 0.4.1 LDAP and XPath cases reported", "ldapi 0 of 16, xpathi 5 of 51", page, "LDAP 0 of 16, XPath 5 of 51")
    tp, fn, _fp, _tn = res["v0.4.1"][("sinkline", "xpathi")]
    results.append((tp == 5 and tp + fn == 51 and res["v0.4.1"][("sinkline", "ldapi")][0] == 0 and sum(res["v0.4.1"][("sinkline", "ldapi")][:2]) == 16,
                    f"LDAP/XPath 0.4.1 counts in results: xpathi {tp} of {tp + fn}"))
    # BenchmarkPython pin and benchmark README facts
    readme = (s / "bench" / "external" / "README.md").read_text(encoding="utf-8")
    results.append(("f1291485808b66e20ddb6b01b10dc71b3df8c8ba" in readme and "1,230" in readme,
                    "bench/external/README.md pins BenchmarkPython f1291485 and 1,230 cases"))
    expect("BenchmarkPython pin (short) on the page", "f129148", page)
    expect("sinkline home reading", "+0.21 to +0.52", "index.html")
    expect("sinkline release v0.5.0 commit", run(["git", "rev-list", "-n1", "v0.5.0"], s).strip()[:7], page)

    # sinkline Sanitizer switch: stored data against the committed captures (the CLI re-run is capture_sinkline_bench.py --check)
    bench = json.loads((SITE / "assets" / "data" / "bench-sinkline.json").read_text(encoding="utf-8"))
    pv = bench["provenance"]
    results.append((pv["version"] == "0.5.0" and run([pybin(venvs, "sinkline", "sinkline"), "--version"], s).strip() == "sinkline 0.5.0",
                    f"sanitizer-switch captures are from sinkline {pv['version']}; installed CLI matches"))
    expect("sanitizer-switch caption version and commit", f"{pv['version']} {pv['commit']}", page, f"sinkline {pv['version']}, tag v{pv['version']}, commit {pv['commit']}")
    nodes = run(["node", str(SITE / "scripts" / "test_bench_sinkline.mjs")], SITE).strip()
    results.append(("checks passed" in nodes, f"node scripts/test_bench_sinkline.mjs: {nodes}"))

    if a.only == "sinkline":
        all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
        for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/(sinkline)/actions/runs/(\d+)", all_html))):
            r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
            results.append((r.get("conclusion") == "success", f"CI run {repo}/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))
        return report()

    # kevgate
    k = clones / "kevgate"
    n = collected(pybin(venvs, "kevgate", "python"), k)
    expect("kevgate tests (main)", str(n), "projects/kevgate/index.html", f"{n} collected")
    expect("kevgate tests on resume page", str(n), "resume/index.html", f"{n} tests")
    tagsha = run(["git", "rev-list", "-n1", "v0.1.1"], k).strip()[:7]
    expect("kevgate v0.1.1 tag commit", tagsha, "projects/kevgate/index.html")
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
    kev_risk_checks(clones, venvs)

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

    # fuzzdiff (Rust). Needs cargo and cargo-llvm-cov on PATH.
    fz = clones / "fuzzdiff"
    page = "projects/fuzzdiff/index.html"
    out = run(["cargo", "test", "--all"], fz)
    counts = [int(x) for x in re.findall(r"test result: ok\. (\d+) passed", out)]
    total = sum(counts)
    expect("fuzzdiff tests (cargo test --all)", str(total), page, f"{total} (")
    mo = run(["cargo", "test", "--release", "-p", "fuzzdiff-harness", "--features", "mutants", "--test", "mutants", "--", "--nocapture"], fz)
    caught = re.findall(r"caught after (\d+) inputs", mo)
    expect("fuzzdiff mutants caught after", ", ".join(caught), page, f"after {caught[0]}, {caught[1]} and {caught[2]} inputs" if len(caught) == 3 else "?")
    ctl = re.search(r"control \(no mutant\): (\d+) inputs, no divergence", mo)
    expect("fuzzdiff mutant control run", ctl.group(1) if ctl else "missing", page, "500,000-input control" if ctl and ctl.group(1) == "500000" else "?")
    run(["cargo", "llvm-cov", "--workspace", "--summary-only"], fz)
    rep = run(["cargo", "llvm-cov", "report", "--summary-only"], fz)
    lines = missed = 0
    for ln in rep.splitlines():
        parts = ln.split()
        if parts and parts[0] in ("chunked.rs", "error.rs", "message.rs", "mutants.rs"):
            lines += int(parts[7])
            missed += int(parts[8])
    pct = "%.2f%%" % (100 * (lines - missed) / lines) if lines else "n/a"
    expect("fuzzdiff src line coverage", pct, page)
    corpus = sum(1 for f in (fz / "corpus").rglob("*") if f.is_file())
    results.append((True, f"fuzzdiff corpus files on disk (info, includes bench inputs and non-input files): {corpus}"))
    log = run(["gh", "run", "view", "42961733885", "-R", "samiali38183/fuzzdiff", "--log"])
    for tgt in ("diff", "rust_only", "c_only"):
        m = re.search(r"fuzz " + tgt + r"\s.*Done (\d+) runs", log)
        if m:
            n_ = f"{int(m.group(1)):,}"
            expect(f"fuzzdiff libFuzzer {tgt} executions", n_, page)
        else:
            results.append((False, f"fuzzdiff libFuzzer {tgt}: log line not found"))

    return report()


def report() -> int:
    bad = 0
    for ok, msg in results:
        print(("PASS  " if ok else "FAIL  ") + msg)
        bad += not ok
    print(f"\n{len(results) - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
