#!/usr/bin/env python3
"""Re-derive the numbers shown on the site from their sources and compare them with the HTML.

Usage:
  python scripts/check_facts.py --clones DIR [--venv tripline=PATH ...] [--go GOBIN]

DIR holds fresh clones named tripline, sinkline, kevgate, kevgate-admit, vulnlab and kev-risk-prioritization.
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
    """`gh api`, retried: GitHub's API fails transiently (outages print warnings that would corrupt the JSON)."""
    import time
    last = ""
    for attempt in range(4):
        p = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
        last = p.stdout
        try:
            data = json.loads(p.stdout)
            if not (isinstance(data, dict) and "message" in data and "documentation_url" in data):  # API error body
                return data
        except json.JSONDecodeError:
            pass
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"gh api {path} failed after retries: {last[:200]!r}")


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


def fuzzdiff_checks(clones: Path) -> None:
    """fuzzdiff v0.2.0. Needs cargo, cargo-llvm-cov, node and the gh CLI. The clone must be at the v0.2.0 tag."""
    fz = clones / "fuzzdiff"
    page = "projects/fuzzdiff/index.html"
    tag = gh("repos/samiali38183/fuzzdiff/releases/latest")["tag_name"]
    expect("fuzzdiff latest release", tag, page)
    expect("fuzzdiff latest release on home", tag, "index.html")
    sha = run(["git", "rev-list", "-n1", "v0.2.0"], fz).strip()
    expect("fuzzdiff v0.2.0 tag commit", sha[:7], page)

    out = run(["cargo", "test", "--all"], fz)
    counts = [int(x) for x in re.findall(r"test result: ok\. (\d+) passed", out)]
    total = sum(counts)
    expect("fuzzdiff tests (cargo test --all)", str(total), page, f"{total} (")
    mo = run(["cargo", "test", "--release", "-p", "fuzzdiff-harness", "--features", "mutants", "--test", "mutants", "--", "--nocapture"], fz)
    caught = re.findall(r"generator caught after (\d+) inputs", mo)
    needle = f"generator after {int(caught[0]):,}, {int(caught[1]):,}, {int(caught[2]):,} and {int(caught[3]):,} inputs" if len(caught) == 4 else "?"
    expect("fuzzdiff seeded bugs caught by the generator after", ", ".join(caught), page, needle)
    over = re.search(r"OverheadRatio: generator did not catch it in (\d+) inputs", mo)
    results.append((bool(over) and "targeted case #1 catches it" in mo and "targeted case #4 catches it" in mo,
                    f"fuzzdiff OverheadRatio not caught by the generator in {over.group(1) if over else '?'} inputs; targeted cases #1 and #4 catch the two that need them"))
    ctl = re.search(r"control \(no mutant\): (\d+) inputs", mo)
    expect("fuzzdiff mutant control run", ctl.group(1) if ctl else "missing", page, "500,000-input control" if ctl and ctl.group(1) == "500000" else "?")
    rep = run(["cargo", "llvm-cov", "--workspace", "--summary-only"], fz)
    lines = missed = 0
    for ln in rep.splitlines():
        parts = ln.split()
        if parts and parts[0].replace("\\", "/") in ("src/chunked.rs", "src/error.rs", "src/message.rs", "src/mutants.rs"):
            lines += int(parts[7])
            missed += int(parts[8])
    pct = "%.2f%%" % (100 * (lines - missed) / lines) if lines else "n/a"
    expect("fuzzdiff src line coverage", pct, page)
    readme = (fz / "README.md").read_text(encoding="utf-8")
    results.append((f"{total} tests pass" in readme, f"fuzzdiff README says {total} tests pass"))
    results.append((pct in readme, f"fuzzdiff README gives line coverage {pct}"))

    # corpus composition
    files = [f for f in (fz / "corpus").rglob("*") if f.is_file() and f.parent.name != "bench"]
    pico = sum(1 for f in files if f.name.startswith("picohttpparser-"))
    hand = sum(1 for f in files if f.name.startswith("hand-"))
    expect("fuzzdiff corpus inputs", str(len(files)), page, f"{len(files)} inputs: {pico} from picohttpparser's own tests, {hand} hand-written")

    # speed ratios from docs/BENCHMARKS.md
    bm = (fz / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
    ratios = [float(m) for m in re.findall(r"\| (\d\.\d\d)x \|", bm)][:4]
    results.append((bool(ratios) and round(min(ratios), 1) == 1.4 and round(max(ratios), 1) == 1.5, f"fuzzdiff head-parsing ratios {ratios}: about 1.4x to 1.5x"))
    expect("fuzzdiff head-parsing speed", "1.4x to 1.5x", page, "about 1.4x to 1.5x slower")

    # three-way comparison: the page uses a verbatim copy of the document's generated blocks
    doc = (fz / "docs" / "DIFFERENTIAL_HTTPARSE.md").read_text(encoding="utf-8")
    for name in ("curated", "sweep"):
        blk = re.search(r"<!-- BEGIN GENERATED: " + name + r" -->\n(.*?)<!-- END GENERATED: " + name + r" -->", doc, re.S)
        mine = (SITE / "assets" / "data" / "fuzzdiff-bench" / f"{name}-table.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        results.append((bool(blk) and blk.group(1).strip() + "\n" == mine, f"fuzzdiff {name} table copy equals docs/DIFFERENTIAL_HTTPARSE.md at the tag"))
    sw = re.search(r"Inputs: (\d+) .*?disagreed on (\d+)\.", doc, re.S)
    expect("fuzzdiff sweep inputs", f"{int(sw.group(1)):,}", page)
    expect("fuzzdiff sweep disagreements", f"{int(sw.group(2)):,}", page)
    expect("fuzzdiff picohttpparser vs fuzzdiff differences", "0", page, "0 differences between picohttpparser and fuzzdiff")

    # bench data against a fresh run, and the parity test
    cap = run([sys.executable, str(SITE / "scripts" / "capture_fuzzdiff_bench.py"), "--work", str(clones), "--check"], SITE).strip()
    results.append((cap.startswith("OK"), f"capture_fuzzdiff_bench.py --check: {cap.splitlines()[-1] if cap else 'no output'}"))
    nodes = run(["node", str(SITE / "scripts" / "test_bench_fuzzdiff.mjs")], SITE).strip()
    results.append(("checks passed" in nodes, f"node scripts/test_bench_fuzzdiff.mjs: {nodes}"))

    # CI: the runs shown (ci on main, the fuzz runs of pull request 3) and the libFuzzer counts of the first fuzz run
    for rid in ("43037960324", "43035685955", "43037421227"):
        r = gh(f"repos/samiali38183/fuzzdiff/actions/runs/{rid}")
        results.append((r.get("conclusion") == "success", f"CI run fuzzdiff/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))
    jobs = gh("repos/samiali38183/fuzzdiff/actions/runs/43037960324/jobs")["jobs"]
    results.append((len(jobs) == 7 and all(j["conclusion"] == "success" for j in jobs), f"fuzzdiff ci run 43037960324: {len(jobs)} jobs, all success ({', '.join(j['name'] for j in jobs)})"))
    log = run(["gh", "run", "view", "43035685955", "-R", "samiali38183/fuzzdiff", "--log"])
    for leg in ("diff", "diff-sse42", "rust_only", "c_only", "c_only-sse42"):
        m = re.search(r"fuzz " + re.escape(leg) + r"\s.*Done (\d+) runs", log)
        if m:
            expect(f"fuzzdiff libFuzzer {leg} executions", f"{int(m.group(1)):,}", page)
        else:
            results.append((False, f"fuzzdiff libFuzzer {leg}: log line not found"))
    mlog = run(["gh", "run", "view", "43037960324", "-R", "samiali38183/fuzzdiff", "--log"])
    miri = sum(int(x) for x in re.findall(r"Miri[^\n]*test result: ok\. (\d+) passed", re.sub(r"\x1b\[[0-9;]*m", "", mlog)))
    expect("fuzzdiff Miri tests", str(miri), page, f"Miri ran on the pure-Rust crate only: {miri} tests")


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


def admit_checks(clones: Path, env_go: str) -> None:
    """kevgate-admit sheet: tests, coverage, parity vectors, release, image, Admission desk data."""
    page = "projects/kevgate-admit/index.html"
    ka = clones / "kevgate-admit"
    tag = gh("repos/samiali38183/kevgate-admit/releases/latest")["tag_name"]
    expect("kevgate-admit latest release", tag, page)
    expect("kevgate-admit latest release on home", tag, "index.html")
    tagsha = run(["git", "rev-list", "-n1", tag], ka).strip()
    head = run(["git", "rev-parse", "HEAD"], ka).strip()
    results.append((head == tagsha, f"kevgate-admit clone HEAD {head[:7]} is the {tag} commit {tagsha[:7]}"))
    expect("kevgate-admit tag commit", tagsha[:7], page)
    pj = run([env_go, "test", "./...", "-json", "-count=1"], ka)
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
    expect("kevgate-admit top-level tests", str(len(top)), page, f"{len(top)} top-level")
    expect("kevgate-admit all tests", str(len(allt)), page, f"{len(allt)} with subtests")
    expect("kevgate-admit tests in the summary box", str(len(top)), page, f"{len(top)} tests, ")
    run([env_go, "test", "./...", "-coverprofile=c.out", "-count=1"], ka)
    cov = run([env_go, "tool", "cover", "-func=c.out"], ka).strip().splitlines()[-1]
    m = re.search(r"([\d.]+)%", cov)
    expect("kevgate-admit coverage", m.group(1) + "%", page)
    expect("kevgate-admit coverage in the summary box", m.group(1) + "%", page, f"{len(top)} tests, {m.group(1)}% coverage")
    vec = json.loads((ka / "internal" / "risk" / "testdata" / "parity_vectors.json").read_text(encoding="utf-8"))
    expect("kevgate-admit parity vectors", str(len(vec)), page, f"{len(vec)} generated vectors")
    try:
        (ka / "c.out").unlink()
    except OSError:
        pass
    img = "sha256:1023382754d9b6b7ca727d47701d9e3bfb5f245a6531e0debd1307ebf9e64195"
    expect("kevgate-admit image digest", img, page)
    bench = json.loads((SITE / "assets/data/admission-bench.json").read_text(encoding="utf-8"))
    results.append((bench["provenance"]["commit"] == tagsha, f"Admission desk data captured at the {tag} commit {bench['provenance']['commit'][:7]}"))
    n1, n2 = len(bench["results"]), len(bench["signed"]["results"])
    expect("Admission desk response counts", f"{n1}+{n2}", page, f"{n1 + n2} recorded responses ({n1} decisions, {n2} with signed evidence)")
    expect("Admission desk scanner entries", str(bench["scanner"]["raw_entries"]), page, f"{bench['scanner']['raw_entries']} entries, 10 findings")
    nodes = run(["node", str(SITE / "scripts" / "test_bench_admission.mjs")], SITE).strip().splitlines()[-1]
    results.append(("checks passed" in nodes, f"node scripts/test_bench_admission.mjs: {nodes}"))
    gen = run([sys.executable, str(SITE / "scripts" / "capture_admission_bench.py"), "--go", env_go, "--check"], SITE)
    gen = next((ln for ln in gen.splitlines() if ln.startswith("checked")), gen.strip()[-200:])
    results.append((gen.endswith("OK"), f"capture_admission_bench.py --check: {gen}"))
    all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
    for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/(kevgate-admit)/actions/runs/(\d+)", all_html))):
        r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
        results.append((r.get("conclusion") == "success", f"CI run {repo}/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))


def vulnlab_checks(clones: Path, venvs: dict[str, str]) -> None:
    """vulnlab v0.1.1 sheet: release, tag commit, test count, sinkline results, CI run, demo lines, bug lines, Lab explorer data."""
    page = "projects/vulnlab/index.html"
    vl = clones / "vulnlab"
    venvs = {k: str(Path(v).resolve()) for k, v in venvs.items()}  # the commands below run in other directories
    py = pybin(venvs, "vulnlab", "python")
    env = dict(os.environ)
    if "vulnlab" in venvs:  # tools/sinkline_check.py and demo.sh call `sinkline` by name: use the venv's, not one on PATH
        env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")
    tag = gh("repos/samiali38183/vulnlab/releases/latest")["tag_name"]
    expect("vulnlab latest release", tag, page)
    expect("vulnlab latest release on home", tag, "index.html")
    tagsha = run(["git", "rev-list", "-n1", tag], vl).strip()
    head = run(["git", "rev-parse", "HEAD"], vl).strip()
    results.append((head == tagsha, f"vulnlab clone HEAD {head[:7]} is the {tag} commit {tagsha[:7]}"))
    expect("vulnlab tag commit", tagsha[:7], page)

    # tests: all collected tests pass
    n = collected(py, vl)
    expect("vulnlab collected tests", str(n), page, f"{n} in all")
    expect("vulnlab tests in the summary box", str(n), page, f"{n} tests pass")
    pt = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=vl, capture_output=True, text=True, env=env).stdout
    m = re.search(r"(\d+) passed", pt)
    results.append((bool(m) and int(m.group(1)) == n and "failed" not in pt, f"vulnlab pytest -q: {pt.strip().splitlines()[-1] if pt.strip() else 'no output'}"))

    # sinkline: findings per lab and version, from a fresh run
    vuln_found = fixed_found = 0
    for lab in sorted((vl / "labs").iterdir()):
        for variant in ("vulnerable", "fixed"):
            out = subprocess.run([pybin(venvs, "vulnlab", "sinkline"), "scan", variant, "--no-color", "--format", "json"], cwd=lab, capture_output=True, text=True, env=env).stdout
            found = len(json.loads(out)["findings"])
            if variant == "vulnerable":
                vuln_found += found > 0
            else:
                fixed_found += found > 0
    reading = f"sinkline {vuln_found} of 3 detected ({fixed_found} false positives on fixes)"
    expect("vulnlab sinkline result", reading, "index.html")
    expect("vulnlab sinkline result on the projects page", reading, "projects/index.html")
    ck = subprocess.run([py, "tools/sinkline_check.py"], cwd=vl, capture_output=True, text=True, env=env)
    results.append((ck.returncode == 0, f"vulnlab tools/sinkline_check.py exit {ck.returncode}"))
    sg = subprocess.run([pybin(venvs, "vulnlab", "sigma"), "check", *sorted(str(x.relative_to(vl)) for x in vl.glob("labs/*/detection/*.yml"))], cwd=vl, capture_output=True, text=True, env=env).stdout
    results.append(("Found 0 errors, 0 condition errors and 0 issues" in sg, "vulnlab sigma check: 0 errors, 0 condition errors, 0 issues"))

    # the demo transcript on the page: every shown pytest and replay line appears in a real run of tools/demo.sh
    demo = subprocess.run(["bash", "tools/demo.sh"], cwd=vl, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env).stdout
    html = (SITE / page).read_text(encoding="utf-8")
    shown = re.search(r'data-label="\$ bash tools/demo.sh[^"]*"><code>(.*?)</code>', html, re.S).group(1)
    import html as _h
    lines = [l for l in _h.unescape(shown).splitlines() if "(full output on Figure 1)" not in l and "(not shown:" not in l]
    missing = [l for l in lines if l.strip() not in demo]
    results.append((not missing and len(lines) > 8, f"vulnlab demo transcript: {len(lines)} lines, {len(missing)} not found in a real run of tools/demo.sh {missing[:2]}"))

    # the vulnerable lines the page quotes, at the lines it names
    for lab, num, text in [("01-ssrf-redirect", 23, "upstream = requests.get(url, timeout=3)"), ("01-ssrf-redirect", 20, "if not host_allowed(url):"),
                           ("02-sqli-order-by", 16, "ORDER BY {sort} {direction}"), ("03-idor-bola", 37, "if current_user() is None:"),
                           ("03-idor-bola", 41, "return jsonify(invoices[object_id])")]:
        src = (vl / "labs" / lab / "vulnerable" / "app.py").read_text(encoding="utf-8").splitlines()[num - 1]
        results.append((text in src, f"vulnlab {lab} vulnerable/app.py line {num} contains {text!r}"))
        expect(f"vulnlab page quotes {lab} line {num}", text, page)

    # the latest run on main is the one on the page
    runs = gh("repos/samiali38183/vulnlab/actions/runs?branch=main&per_page=1")["workflow_runs"]
    rid = str(runs[0]["id"]) if runs else "?"
    results.append((bool(runs) and runs[0]["conclusion"] == "success", f"vulnlab latest main run {rid}: {runs[0]['name']!r} {runs[0]['conclusion']} sha {runs[0]['head_sha'][:7]}" if runs else "no runs"))
    expect("vulnlab latest CI run on the page", rid, page, f"run {rid}")
    expect("vulnlab latest CI run on home", rid, "index.html", f"run {rid}")

    # the stored bench data equals a fresh run, and the page equals the stored data
    cap = subprocess.run([sys.executable, str(SITE / "scripts" / "capture_vulnlab_bench.py"), "--check", "--clone", str(vl)] + (["--venv", venvs["vulnlab"]] if "vulnlab" in venvs else []),
                         capture_output=True, text=True, env=env)
    results.append((cap.returncode == 0, "capture_vulnlab_bench.py --check: " + (cap.stdout.strip().splitlines() or ["no output"])[-1]))
    nd = subprocess.run(["node", str(SITE / "scripts" / "test_bench_vulnlab.mjs")], capture_output=True, text=True)
    results.append((nd.returncode == 0, "test_bench_vulnlab.mjs: " + (nd.stdout.strip().splitlines() or [nd.stderr[:120]])[-1]))
    all_html = "".join(x.read_text(encoding="utf-8") for x in SITE.rglob("*.html") if "content" not in x.parts)
    for repo, rid2 in sorted(set(re.findall(r"github\.com/samiali38183/(vulnlab)/actions/runs/(\d+)", all_html))):
        r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid2}")
        results.append((r.get("conclusion") == "success", f"CI run {repo}/{rid2}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))


def kevgate_checks(clones: Path, venvs: dict[str, str]) -> None:
    """kevgate v0.1.1 sheet: tests, coverage, tag commit, mutants, latest main runs, release image, matrix data and page."""
    page = "projects/kevgate/index.html"
    k = clones / "kevgate"
    py = pybin(venvs, "kevgate", "python")
    tag = gh("repos/samiali38183/kevgate/releases/latest")["tag_name"]
    expect("kevgate latest release", tag, page)
    expect("kevgate latest release on home", tag, "index.html")
    tagsha = run(["git", "rev-list", "-n1", tag], k).strip()
    expect("kevgate tag commit", tagsha[:7], page)
    n = collected(py, k)
    expect("kevgate tests", str(n), page, f"{n} collected")
    expect("kevgate tests on resume page", str(n), "resume/index.html", f"{n} tests")
    cov = run([py, "-m", "pytest", "--cov", "-p", "no:cacheprovider"], k)
    m = re.search(r"Total coverage: ([\d.]+)%", cov)
    results.append((bool(m) and f"{n} passed" in cov, f"kevgate pytest --cov: {n} passed, coverage {m.group(1) if m else '?'}%"))
    if m:
        expect("kevgate coverage", m.group(1) + "%", page)
    for tool, cmd in (("ruff check", [py, "-m", "ruff", "check", "."]), ("mypy --strict src", [py, "-m", "mypy", "--strict", "src"])):
        p = subprocess.run(cmd, cwd=k, capture_output=True, text=True)
        results.append((p.returncode == 0, f"kevgate {tool} exit {p.returncode}"))
    # latest push runs on main per workflow: the page links the latest green one
    for wf in ("ci", "security", "deploy-kind", "terraform"):
        runs = gh(f"repos/samiali38183/kevgate/actions/workflows/{wf}.yml/runs?branch=main&event=push&per_page=1")["workflow_runs"]
        rid = str(runs[0]["id"])
        results.append((runs[0]["conclusion"] == "success", f"kevgate latest {wf} run on main {rid}: {runs[0]['conclusion']} sha {runs[0]['head_sha'][:7]}"))
        expect(f"kevgate latest {wf} run on the page", rid, page, f"run {rid}")
    rel = gh("repos/samiali38183/kevgate/actions/runs/42960813836")
    results.append((rel["conclusion"] == "success" and rel["head_branch"] == tag, f"kevgate release run 42960813836: {rel['conclusion']} on {rel['head_branch']}"))
    mut = subprocess.run([sys.executable, str(SITE / "scripts" / "rerun_kevgate_mutants.py"), "--clone", str(k), "--python", py], capture_output=True, text=True)
    results.append((mut.returncode == 0, "rerun_kevgate_mutants.py: " + (mut.stdout.strip().splitlines() or ["no output"])[-1]))
    cap = subprocess.run([sys.executable, str(SITE / "scripts" / "capture_kevgate_bench.py"), "--check", "--clone", str(k), "--venv", str(Path(py).parent.parent)],
                         capture_output=True, text=True)
    results.append((cap.returncode == 0, "capture_kevgate_bench.py --check: " + (cap.stdout.strip().splitlines() or [cap.stderr[-120:]])[-1]))
    nd = subprocess.run(["node", str(SITE / "scripts" / "test_bench_kevgate.mjs")], capture_output=True, text=True)
    results.append((nd.returncode == 0, "test_bench_kevgate.mjs: " + (nd.stdout.strip().splitlines() or [nd.stderr[:120]])[-1]))
    data = json.loads((SITE / "assets/data/kevgate-bench.json").read_text(encoding="utf-8"))
    expect("kevgate matrix control count", str(len(data["controls"])), page, f"Every one of {len(data['controls'])} controls")
    expect("kevgate matrix cited tests", str(data["meta"]["tests_cited"]), page, f"{data['meta']['tests_cited']} cited tests")
    expect("kevgate matrix collected tests", str(data["meta"]["tests_total"]), page, f"of {data['meta']['tests_total']} collected")
    all_html = "".join(x.read_text(encoding="utf-8") for x in SITE.rglob("*.html") if "content" not in x.parts)
    for rid in sorted(set(re.findall(r"github\.com/samiali38183/kevgate/actions/runs/(\d+)", all_html))):
        r = gh(f"repos/samiali38183/kevgate/actions/runs/{rid}")
        results.append((r.get("conclusion") == "success", f"CI run kevgate/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')} sha={r.get('head_sha', '')[:7]}"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clones", required=True)
    ap.add_argument("--venv", action="append", default=[])
    ap.add_argument("--go", default="go")
    ap.add_argument("--only", choices=["sinkline", "tripline", "kev", "fuzzdiff", "admit", "vulnlab", "kevgate"], help="run only one project's checks (when the other toolchains are not installed)")
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

    if a.only == "fuzzdiff":
        fuzzdiff_checks(clones)
        return report()

    if a.only == "kev":
        kev_risk_checks(clones, venvs)
        return report()
    if a.only == "admit":
        admit_checks(clones, a.go)
        return report()
    if a.only == "vulnlab":
        vulnlab_checks(clones, venvs)
        return report()
    if a.only == "kevgate":
        kevgate_checks(clones, venvs)
        return report()

    # tripline
    if a.only in (None, "tripline"):
        t = clones / "tripline"
        sc_all = json.loads((t / "docs" / "scorecard.json").read_text(encoding="utf-8"))
        sc = sc_all["totals"]
        scn = sc_all["scenarios"]
        expect("tripline gate", f"{sc['passed']} passed, {sc['failed']} failed, {sc['pending']} pending", "projects/tripline/index.html")
        expect("tripline scenarios", str(sc["scenarios"]), "projects/tripline/index.html", f"{sc['scenarios']} scenarios")
        pct = round(sc["weighted_coverage"] * 100)
        expect("tripline weighted coverage", f"{pct}%", "projects/tripline/index.html")
        # The 98% must never appear without the split (52% on unmodified SigmaHQ rules alone).
        pts = sum(r["weight"] for r in scn)
        got = round(sc["weighted_coverage"] * pts)
        vend = round(sc["weighted_coverage_vendored"] * pts)
        expect("tripline weighted points", f"{got} of {pts}", "projects/tripline/index.html", f"{got} of {pts}")
        expect("tripline vendored-only split", f"{round(sc['weighted_coverage_vendored'] * 100)}% ({vend} of {pts}, {sc['passed_vendored_only']} scenarios)",
               "projects/tripline/index.html", f"{round(sc['weighted_coverage_vendored'] * 100)}% ({vend} of {pts}, {sc['passed_vendored_only']} scenarios)")
        authored = sum(r["weight"] for r in scn if r["status"] == "passed" and r["needs_authored_rule"])
        expect("tripline authored-rule points", f"{authored} of {pts}", "projects/tripline/index.html", f"({authored} of {pts} weight points)")
        for pg in ("projects/tripline/index.html", "projects/index.html", "index.html"):
            html_text = text_of(pg)
            for m in re.finditer(r"(?<![0-9])98%", html_text):
                near = html_text[max(0, m.start() - 160): m.end() + 260]
                results.append(("52%" in near, f"98% shown with the 52% split within 400 characters in {pg} (at offset {m.start()})"))
        # weights: points that follow the published ranking (docs/weights.md)
        ranked = set(re.findall(r"^\d+\. (T[\d.]+)", (t / "docs" / "weights.md").read_text(encoding="utf-8"), re.M))
        follow = sum(r["weight"] for r in scn if r["technique"] in ranked)
        expect("tripline weight points following the ranking", f"{follow} of {pts}", "projects/tripline/index.html", f"{follow} of {pts} points follow")
        ben = sc_all["benign"]
        nb = ben["events"]
        ev_rules = [r for r in ben["rules"] if r["applicable"]]
        fp = sum(r["matched"] for r in ben["rules"])
        fp_rules = sum(1 for r in ben["rules"] if r["matched"])
        expect("tripline benign corpus", f"{fp} matches from {fp_rules} of {len(ev_rules)} evaluated rules, {nb} events", "projects/tripline/index.html",
               f"{fp} matches from {fp_rules} of {len(ev_rules)} evaluated rules on {nb} events")
        expect("tripline benign not evaluated", f"{len(ben['rules']) - len(ev_rules)} of {len(ben['rules'])}", "projects/tripline/index.html",
               f"{len(ben['rules']) - len(ev_rules)} of {len(ben['rules'])} rules not evaluated")
        # evasion sweep: the page's strip data must equal the variants in docs/robustness.json (sweep re-run: tripline robustness)
        rob = json.loads((t / "docs" / "robustness.json").read_text(encoding="utf-8"))
        page_sets = json.loads((SITE / "content/data/projects.json").read_text(encoding="utf-8"))["projects"]["tripline"]["strip_sets"]
        want = {}
        for scn_r in rob["scenarios"]:
            exp_ids = {r["rule_id"] for r in scn_r["rules"] if r["expected"]}
            for cmd in (True, False):
                vs = [v for v in scn_r["variants"] if (v["kind"] == "cmdline") == cmd]
                if not vs:
                    continue
                runs: list[list] = []
                for v in vs:
                    st = "hit" if any(v["caught"].get(i) for i in exp_ids) else "miss"
                    if runs and runs[-1][0] == st:
                        runs[-1][1] += 1
                    else:
                        runs.append([st, 1])
                want[(scn_r["technique"], cmd)] = runs
        rows = {r["label"]: r["runs"] for r in page_sets["evasion"]["rows"]}
        got_rows = [rows["Cron"], rows["History"], rows["Setuid"], rows["Setuid, other tools"]]
        want_rows = [want[("T1053.003", True)], want[("T1070.003", True)], want[("T1548.001", True)], want[("T1548.001", False)]]
        results.append((got_rows == want_rows, "evasion strips equal the variants in docs/robustness.json (per scenario, in order)"))
        n_cmd = sum(n for rr in got_rows[:3] for _, n in rr)
        n_hit = sum(n for rr in got_rows[:3] for st, n in rr if st == "hit")
        expect("tripline evasion sweep", f"{n_hit} of {n_cmd}", "projects/tripline/index.html", f"{n_hit} of {n_cmd} command-line variants")
        bsum = sum(n for _, n in page_sets["benign"]["rows"][0]["runs"])
        results.append((bsum == nb and sum(n for st, n in page_sets["benign"]["rows"][0]["runs"] if st == "fp") == fp, f"benign strip: {bsum} events, {fp} matches"))
        out = run([pybin(venvs, "tripline", "tripline"), "replay", "--all"], t)
        ps = len(re.findall(r"^\[\s+PASS\]", out, re.M))
        pe = len(re.findall(r"^\[PENDING\]", out, re.M))
        results.append((ps == sc["passed"] and pe == sc["pending"] and "gate passed" in out,
                        f"tripline replay --all output: {ps} PASS, {pe} PENDING, gate passed={'gate passed' in out}"))
        n = collected(pybin(venvs, "tripline", "python"), t)
        expect("tripline tests (pytest collection)", str(n), "projects/tripline/index.html", f"{n} (91% line+branch")
        cov = run([pybin(venvs, "tripline", "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--cov=tripline", "--cov-branch"], t)
        mcov = re.search(r"^TOTAL\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)%", cov, re.M)
        results.append((bool(mcov) and mcov.group(1) == "91", f"tripline coverage (line+branch) {mcov.group(1) + '%' if mcov else 'not measured'}, page says 91%"))
        expect("tripline tests on resume page", str(n), "resume/index.html", f"{n} tests")
        code = (
            "from pathlib import Path\n"
            "from tripline.engine.rules import load_rules, evaluate\n"
            "from tripline.replay import load_fixture_events\n"
            "from tripline.scenarios import load_scenarios\n"
            "from tripline.logsource import normalize\n"
            "root=Path('.')\n"
            "sc={s.id:s for s in load_scenarios(root/'scenarios')}['t1548-001-setuid-setgid']\n"
            "ev=load_fixture_events(sc,root)\n"
            "rs={r.id:r for r in load_rules(root/'rules'/'sigma').rules}\n"
            "for rid in ('c21c4eaa-ba2e-419a-92b2-8371703cbe21','7f3c2b1a-6d4e-4a9b-9c8d-1e2f3a4b5c6d'):\n"
            "    res=[evaluate(rs[rid],e) for e in ev]\n"
            "    ne=[normalize(e) for e in ev]\n"
            "    ok=[(x is not None) for x in res]\n"
            "    atk=[x for x,n,k in zip(res,ne,ok) if k and n['Image'].endswith('/chmod')]\n"
            "    wrap=sum(1 for n,k in zip(ne,ok) if k and not n['Image'].endswith('/chmod') and 'chmod' in n['CommandLine'])\n"
            "    print(sum(x is not None for x in res), sum(x is True for x in res), len(atk), sum(x is True for x in atk), wrap)\n"
        )
        o = run([pybin(venvs, "tripline", "python"), "-c", code], t).split()
        if len(o) == 10:
            # per rule: applicable events, flagged events, attack events (chmod executions), flagged attack events, wrapper events
            (tot, s_all, n_atk, s_atk, n_wrap), (tot2, r_all, n_atk2, r_atk, n_wrap2) = list(map(int, o[:5])), list(map(int, o[5:]))
            results.append((tot == tot2 == 36 and n_atk == n_atk2 == 2 and n_wrap == n_wrap2 == 4 and (s_atk, r_atk) == (0, 2) and (s_all, r_all) == (0, 2),
                            f"F-001 counts from the fixture: {tot} events, {n_atk} attack events, {n_wrap} wrapper lines; stock flagged {s_atk}, replacement flagged {r_atk}"))
            expect("tripline stock rule on the attack events", f"{s_atk} of the {n_atk} attack events", "projects/tripline/index.html")
            expect("tripline replacement rule on the attack events", f"{r_atk} of {n_atk}", "projects/tripline/index.html")
            expect("tripline hero reading on the home page", f"flagged {s_atk} of those {n_atk}", "index.html")
            expect("tripline resume text", f"flagged {s_atk} of the {n_atk} attack events among {tot} recorded events", "resume/index.html")
            expect("tripline about text", f"flagged {s_atk} of the {n_atk} attack events among {tot} recorded events", "about/index.html")
        else:
            results.append((False, f"tripline F-001 derivation failed: {o}"))
        # tripline Rule bench: data file against the clone's rule YAML and the page text
        import yaml
        bd = json.loads((SITE / "assets/data/bench-tripline.json").read_text(encoding="utf-8"))
        ys = yaml.safe_load((t / bd["meta"]["stock"]["file"]).read_text(encoding="utf-8"))["detection"]
        yc = yaml.safe_load((t / bd["meta"]["custom"]["file"]).read_text(encoding="utf-8"))["detection"]
        img_sel = yc["selection_image"]["Image|endswith"]
        same = (bd["stock"]["perm"] == ys["selection_perm"]["CommandLine|contains"]
                and bd["stock"]["root"] == [ys["selection_root"]["CommandLine|contains"]]
                and bd["custom"] == {"image": [img_sel] if isinstance(img_sel, str) else list(img_sel), "symbolic": yc["selection_symbolic"]["CommandLine|re"],
                                     "octal": yc["selection_octal"]["CommandLine|re"], "filter": yc["filter_tmp_runner"]["CommandLine|re"]})
        results.append((same, "bench rule patterns equal the YAML in the tripline clone"))
        ev = bd["events"]
        results.append((len(ev) == 36 and sum(e["s"] for e in ev) == 0 and sum(e["r"] for e in ev) == 2, "bench events: 36, stock 0, replacement 2"))
        expect("bench parity cases", str(bd["meta"]["parity_cases"]), "projects/tripline/index.html", f"on {bd['meta']['parity_cases']} command lines")

    if a.only == "tripline":
        all_html = "".join(p.read_text(encoding="utf-8") for p in SITE.rglob("*.html") if "content" not in p.parts)
        for repo, rid in sorted(set(re.findall(r"github\.com/samiali38183/(tripline)/actions/runs/(\d+)", all_html))):
            r = gh(f"repos/samiali38183/{repo}/actions/runs/{rid}")
            red = rid in {"41838714456", "42917025570", "43090565998"}  # recording runs, red by design
            results.append((r.get("conclusion") == ("failure" if red else "success"), f"CI run {repo}/{rid}: conclusion={r.get('conclusion')}{' (expected red)' if red else ''}"))
        return report()

    # sinkline (the clone must be at the v0.5.1 tag or main at that commit)
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
    expect("sinkline tests", str(n), "projects/sinkline/index.html", f"{n} on main")
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
    expect("sinkline release v0.5.1 commit", run(["git", "rev-list", "-n1", "v0.5.1"], s).strip()[:7], page)

    # sinkline Sanitizer switch: stored data against the committed captures (the CLI re-run is capture_sinkline_bench.py --check)
    bench = json.loads((SITE / "assets" / "data" / "bench-sinkline.json").read_text(encoding="utf-8"))
    pv = bench["provenance"]
    results.append((pv["version"] == "0.5.1" and run([pybin(venvs, "sinkline", "sinkline"), "--version"], s).strip() == "sinkline 0.5.1",
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
        expected_red = rid in {"41838714456", "42917025570", "43090565998"}
        results.append((r.get("conclusion") == ("failure" if expected_red else "success"),
                        f"CI run {repo}/{rid}: workflow {r.get('name')!r} conclusion={r.get('conclusion')}{' (expected red, linked as the recording source)' if expected_red else ''} sha={r.get('head_sha', '')[:7]}"))

    # kev-risk-prioritization
    kev_risk_checks(clones, venvs)

    # kevgate-admit (Go)
    admit_checks(clones, a.go)

    # fuzzdiff (Rust). Needs cargo, cargo-llvm-cov, node.
    fuzzdiff_checks(clones)
    vulnlab_checks(clones, venvs)
    kevgate_checks(clones, venvs)

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
