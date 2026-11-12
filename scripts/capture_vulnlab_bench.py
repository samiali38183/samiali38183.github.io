#!/usr/bin/env python3
"""Capture or verify the recorded runs shown by the "Lab explorer" bench on the vulnlab page.

  python scripts/capture_vulnlab_bench.py                      # clone, install, run, write the data
  python scripts/capture_vulnlab_bench.py --check              # clone, install, run, compare, change nothing
  python scripts/capture_vulnlab_bench.py --clone DIR --venv DIR [--check]   # reuse a clone at the tag and a venv

What it does (needs git, network access to GitHub and Python 3.12):
  1. Clones https://github.com/samiali38183/vulnlab into a scratch directory, checks out the tag v0.1.1 and refuses to
     continue if the commit is not the one recorded below. The public repository is never modified.
  2. Creates a virtual environment and installs requirements.lock (the exact versions CI uses, including sinkline and
     tripline at pinned commits) and the project itself. No Docker; the labs are plain Python processes on loopback.
  3. Runs `python -m pytest -v -p no:cacheprovider` and records every test result of the three labs by name (and the
     count of the 26 safety and harness tests under tests/). Every lab test must be listed in TESTS below, so a test added
     upstream makes the script fail instead of being silently left out.
  4. Runs `sinkline scan <variant> --no-color` and `--format json` from each lab directory for the vulnerable and the fixed
     version, and checks that the text equals the file the repository itself recorded under labs/*/sinkline/.
  5. Replays each lab's Sigma rule over its recorded attack and benign logs with `python -m vulnlab_common.replay` and
     records the printed counts. The raw logs are not copied: they hold the lab's request strings.
  6. Runs `python tools/sinkline_check.py` and `sigma check labs/*/detection/*.yml` and records that they pass.
  7. Reads the two app.py files of each lab, marks the lines that differ, and writes assets/data/vulnlab-bench.json.

Nothing in the results is edited by hand. The short descriptions in LABS and the roles in TESTS are labels for display; they are
checked against the repository where a check is possible (the vulnerable line named in each README, the test names).
--check exits 1 if the stored file differs from a fresh run (the date and the Python and OS strings are provenance and are not
compared). Prints the commit, Python, pytest, sinkline, tripline and pySigma versions it used.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "vulnlab-bench.json"

REPO_URL = "https://github.com/samiali38183/vulnlab"
TAG = "v0.1.1"
COMMIT = "dd2665d7cdf0ef300846014a5c4a775e3e1dd6d4"
CAPTURED = "2026-11-11"
CI_RUN = "43134837698"

# Display labels. `bug` is the line the lab's README names as the vulnerable line; it is checked against the README and the
# source text below. `note` explains a sinkline result that is not a plain finding.
LABS = [
    {
        "id": "01-ssrf-redirect", "n": "01", "title": "SSRF through a redirect", "cwe": "CWE-918",
        "bug": 23, "bug_text": "requests.get(url", "bug_readme": "app.py:23",
        "vulnerable": "The preview endpoint checks the host of the URL it was given once, then fetches it with a client that follows redirects on its own.",
        "fixed": "The app follows redirects itself, at most three hops, and checks every hop's host and resolved address before connecting to that address.",
        "impact": "The preview endpoint returned the internal service's marker, reached through a redirect on an allowed host.",
        "blocked": "Both the direct and the redirected request were refused and the internal service was never contacted.",
        "sinkline_note": {"fixed": "False positive. sinkline does not recognize a custom allow-list or address pinning as a sanitizer."},
    },
    {
        "id": "02-sqli-order-by", "n": "02", "title": "SQL injection in ORDER BY", "cwe": "CWE-89",
        "bug": 16, "bug_text": "ORDER BY {sort}", "bug_readme": "# line 16",
        "vulnerable": "The search text is bound as a query parameter, but the sort column is pasted into the SQL string.",
        "fixed": "The sort value is looked up in a dictionary of columns the application owns; anything else is a 400.",
        "impact": "A sort value made a second table decide the order of the rows that came back.",
        "blocked": "The same sort values got a 400 and nothing from the second table appeared in a response.",
        "sinkline_note": {"fixed": "False positive. sinkline treats the allow-list dictionary lookup as an unknown call and assumes passthrough."},
    },
    {
        "id": "03-idor-bola", "n": "03", "title": "IDOR / broken object-level authorization", "cwe": "CWE-639",
        "bug": 41, "bug_text": "jsonify(invoices[object_id])", "bug_readme": "jsonify(invoices[object_id])  # line",  # the README still says "line 38" (v0.1.1); the line is 41
        "vulnerable": "The read-by-id route checks that someone is logged in but not that the invoice is theirs; the list and update routes do check.",
        "fixed": "One helper checks ownership and every by-id route goes through it; a record that is not yours answers 404.",
        "impact": "A logged-in user received another user's invoice, including its memo, and every one of the eight ids answered 200.",
        "blocked": "Every record the user did not own answered 404 on read and on update, and the other user's memo never appeared.",
        "sinkline_note": {
            "vulnerable": "Not reported, as the write-up expects: a missing authorization check is not a taint flow.",
        },
    },
]

# Every lab test, by pytest function name (and parameter, where it differs by version): (version, role).
ROLES = {
    "impact": "Impact demonstrated",
    "inconsistency": "Update route already checks the owner",
    "blocked": "Impact blocked",
    "feature": "Feature still works",
    "login": "Login required",
    "detect": "Detection replay",
    "malformed": "Malformed input answered with 400",
    "forbidden": "Well-formed request for another host still refused",
    "pinning": "Address check enforced (test fails if it is removed)",
    "stricter": "Fixed version stricter on odd sort values, by design",
    "anon": "Same answer for existing and missing ids",
    "badlogin": "Unknown users and malformed logins rejected",
}
TESTS = {
    ("01-ssrf-redirect", "test_vulnerable_service_returns_internal_marker_via_allowed_redirect", ""): ("vulnerable", "impact"),
    ("01-ssrf-redirect", "test_fixed_service_does_not_return_internal_marker", ""): ("fixed", "blocked"),
    ("01-ssrf-redirect", "test_fixed_service_still_previews_pages_and_follows_allowed_redirects", ""): ("fixed", "feature"),
    ("01-ssrf-redirect", "test_fixed_service_answers_400_to_every_malformed_url", "*"): ("fixed", "malformed"),
    ("01-ssrf-redirect", "test_fixed_service_answers_400_to_a_malformed_redirect_target", "*"): ("fixed", "malformed"),
    ("01-ssrf-redirect", "test_fixed_service_keeps_403_for_well_formed_urls_on_other_hosts", ""): ("fixed", "forbidden"),
    ("01-ssrf-redirect", "test_address_pinning_refuses_a_host_whose_address_is_not_approved", ""): ("fixed", "pinning"),
    ("01-ssrf-redirect", "test_detection_rule_fires_on_recorded_attack_not_on_benign_traffic", ""): (None, "detect"),
    ("02-sqli-order-by", "test_vulnerable_sort_parameter_lets_another_table_decide_the_order", ""): ("vulnerable", "impact"),
    ("02-sqli-order-by", "test_fixed_endpoint_rejects_non_column_sort_values", "*"): ("fixed", "blocked"),
    ("02-sqli-order-by", "test_fixed_endpoint_is_stricter_than_the_vulnerable_one_on_legitimate_looking_values", "*"): ("fixed", "stricter"),
    ("02-sqli-order-by", "test_fixed_endpoint_keeps_normal_sorting_and_filtering", ""): ("fixed", "feature"),
    ("02-sqli-order-by", "test_detection_rule_fires_on_recorded_attack_not_on_benign_traffic", ""): (None, "detect"),
    ("03-idor-bola", "test_vulnerable_api_returns_another_users_record", ""): ("vulnerable", "impact"),
    ("03-idor-bola", "test_vulnerable_patch_route_already_checks_ownership", ""): ("vulnerable", "inconsistency"),
    ("03-idor-bola", "test_requests_without_a_login_are_rejected", "vulnerable"): ("vulnerable", "login"),
    ("03-idor-bola", "test_requests_without_a_login_are_rejected", "fixed"): ("fixed", "login"),
    ("03-idor-bola", "test_anonymous_callers_cannot_tell_existing_ids_from_missing_ones", "vulnerable"): ("vulnerable", "anon"),
    ("03-idor-bola", "test_anonymous_callers_cannot_tell_existing_ids_from_missing_ones", "fixed"): ("fixed", "anon"),
    ("03-idor-bola", "test_login_rejects_unknown_users_and_malformed_bodies", "*-vulnerable"): ("vulnerable", "badlogin"),
    ("03-idor-bola", "test_login_rejects_unknown_users_and_malformed_bodies", "*-fixed"): ("fixed", "badlogin"),
    ("03-idor-bola", "test_login_rejects_known_user_with_missing_or_non_string_password", "*-vulnerable"): ("vulnerable", "badlogin"),
    ("03-idor-bola", "test_login_rejects_known_user_with_missing_or_non_string_password", "*-fixed"): ("fixed", "badlogin"),
    ("03-idor-bola", "test_fixed_api_hides_other_users_records_on_every_route", ""): ("fixed", "blocked"),
    ("03-idor-bola", "test_fixed_api_still_serves_owners_their_own_records", ""): ("fixed", "feature"),
    ("03-idor-bola", "test_detection_rule_fires_on_recorded_enumeration_not_on_benign_traffic", ""): (None, "detect"),
}
STILL_VISIBLE = "is still visible in the log"   # assertion in the fixed-service tests: the rule still fires there


def param_matches(pattern: str, param: str) -> bool:
    """TESTS keys: "" no parameter, an exact parameter, "*" any, or "*-vulnerable" / "*-fixed" (parameter ends with that)."""
    if pattern == "*":
        return True
    if pattern.startswith("*-"):
        return param.endswith(pattern[1:])
    return param == pattern


def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None, ok: tuple[int, ...] = (0,)) -> tuple[str, int]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, env=env, check=False)
    out = p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if p.returncode not in ok:
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n{out}\n{p.stderr.decode('utf-8', 'replace')}")
    return out, p.returncode


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def venv_bin(venv: Path, exe: str) -> str:
    sub, ext = ("Scripts", ".exe") if os.name == "nt" else ("bin", "")
    return str(venv / sub / (exe + ext))


def changed_lines(base: str, code: str) -> list[int]:
    """1-based lines of `code` that do not appear in `base` (plain difflib; display only)."""
    a, b = base.splitlines(), code.splitlines()
    out: list[int] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(range(j1 + 1, j2 + 1))
    return out


def parse_pytest(out: str) -> tuple[list[dict], int, int]:
    """Return (lab results, tests/ pass count, total passed) from `pytest -v` output."""
    rows, safety = [], 0
    for line in out.splitlines():
        m = re.match(r"^(\S+?)::(\S+?)(?:\[(.*)\])? (PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s+\[\s*\d+%\]$", line)
        if not m:
            continue
        path, name, param, state = m.groups()
        if path.startswith("tests/"):
            safety += state == "PASSED"
        else:
            rows.append({"lab": path.split("/")[1], "name": name, "param": param or "", "state": state})
    summary = re.search(r"=+ (\d+) passed in [\d.]+s(?: \([\d:]+\))? =+", out)
    if not summary:
        raise SystemExit("pytest did not finish with 'N passed':\n" + out[-600:])
    return rows, safety, int(summary.group(1))


def build(clone: Path, venv: Path) -> dict:
    py = venv_bin(venv, "python")
    commit = sh(["git", "rev-parse", "HEAD"], clone)[0].strip()
    if commit != COMMIT:
        raise SystemExit(f"clone is at {commit}, expected {TAG} = {COMMIT}")
    if sh(["git", "status", "--porcelain"], clone)[0].strip():
        raise SystemExit("the clone has local changes; refusing to record")

    def ver(pkg: str) -> str:
        out = sh([py, "-m", "pip", "show", pkg], clone)[0]
        return re.search(r"^Version: (.+)$", out, re.M).group(1).strip()

    versions = {"python": sh([py, "-c", "import platform;print(platform.python_version())"])[0].strip(),
                "pytest": ver("pytest"), "sinkline": ver("sinkline"), "tripline": ver("tripline"), "pysigma": ver("pySigma")}
    if not versions["python"].startswith("3.12."):
        raise SystemExit(f"Python 3.12 is required, got {versions['python']}")
    sinkline_cli = venv_bin(venv, "sinkline")
    sv = sh([sinkline_cli, "--version"])[0].strip()
    if sv != "sinkline " + versions["sinkline"]:
        raise SystemExit(f"unexpected sinkline version output {sv!r}")

    # tests
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    env.pop("VULNLAB_RECORD", None)
    # tools/sinkline_check.py and the tests call `sinkline` by name: make sure it is the one in the venv, not one on PATH.
    env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")
    out, _ = sh([py, "-m", "pytest", "-v", "-p", "no:cacheprovider"], clone, env=env)
    lab_rows, safety, passed = parse_pytest(out)
    if any(r["state"] != "PASSED" for r in lab_rows):
        raise SystemExit("a lab test did not pass:\n" + out[-1500:])
    if sh(["git", "status", "--porcelain"], clone)[0].strip():
        raise SystemExit("running the tests changed files in the clone")

    # sinkline, repository checks
    sh([py, "tools/sinkline_check.py"], clone, env=env)
    sig_out, _ = sh([venv_bin(venv, "sigma"), "check", *sorted(str(p.relative_to(clone)) for p in clone.glob("labs/*/detection/*.yml"))], clone)
    sig_sum = re.search(r"Found (\d+) errors, (\d+) condition errors and (\d+) issues", sig_out)
    if not sig_sum or sig_sum.groups() != ("0", "0", "0"):
        raise SystemExit("sigma check reported problems:\n" + sig_out)

    labs = []
    for meta in LABS:
        lab = clone / "labs" / meta["id"]
        readme = read(lab / "README.md")
        test_src = read(lab / "test_lab.py")
        rows = [r for r in lab_rows if r["lab"] == meta["id"]]
        # tests, grouped by (name, version)
        by_version: dict[str, list[dict]] = {"vulnerable": [], "fixed": []}
        detect = None
        seen_keys = set()
        for r in rows:
            keys = [k for k in TESTS if k[0] == meta["id"] and k[1] == r["name"] and param_matches(k[2], r["param"]) and (k[2] != "*" or r["param"] != "")]
            keys += [k for k in TESTS if k[0] == meta["id"] and k[1] == r["name"] and k[2] == "" and r["param"] == ""]
            keys = list(dict.fromkeys(keys))
            if len(keys) != 1:
                raise SystemExit(f"test {r['name']}[{r['param']}] in {meta['id']} matches {len(keys)} entries of TESTS (need exactly one)")
            seen_keys.add(keys[0])
        for key in TESTS:
            if key[0] == meta["id"] and key not in seen_keys:
                raise SystemExit(f"listed test {key} did not run")
        for key, (version, role) in TESTS.items():
            if key[0] != meta["id"]:
                continue
            cases = [r for r in rows if r["name"] == key[1] and param_matches(key[2], r["param"]) and (key[2] != "" or r["param"] == "")]
            entry = {"name": key[1] + (f"[{key[2]}]" if key[2] != "" and not key[2].startswith("*") else ""), "role": role, "cases": len(cases),
                     "passed": sum(c["state"] == "PASSED" for c in cases)}
            if role == "detect":
                detect = entry
            else:
                by_version[version].append(entry)

        # detection replay
        det_dir = lab / "detection"
        rule = next(det_dir.glob("*.yml"))
        rule_text = read(rule)
        titles = re.findall(r"^title: (.+)$", rule_text, re.M)
        corr = None
        if re.search(r"^correlation:", rule_text, re.M):
            corr = {
                "type": re.search(r"^  type: (\w+)", rule_text, re.M).group(1),
                "group_by": re.search(r"group-by:\n    - (\w+)", rule_text).group(1),
                "timespan": re.search(r"^  timespan: (\S+)", rule_text, re.M).group(1),
                "gte": int(re.search(r"gte: (\d+)", rule_text).group(1)),
                "field": re.search(r"field: (\w+)", rule_text).group(1),
            }
        replays = {}
        for kind in ("attack", "benign"):
            log = det_dir / f"sample_{kind}.ndjson"
            text, _ = sh([py, "-m", "vulnlab_common.replay", str(rule.relative_to(clone)), str(log.relative_to(clone))], clone)
            head = re.match(r"^sample_\w+\.ndjson: (\d+) events, (\d+) alert\(s\)\n", text)
            alerts = re.findall(r"^  ALERT '(.+)': (\d+) matching event\(s\)$", text, re.M)
            replays[kind] = {"events": int(head.group(1)), "alerts": int(head.group(2)), "out": text,
                             "matching": [int(n) for _t, n in alerts], "titles": [t for t, _n in alerts]}
        for kind, want in (("attack", "vulnerable"), ("benign", "fixed")):
            # which test wrote the recorded sample (VULNLAB_RECORD copies the access log of its own run)
            at = test_src.index(f"sample_{kind}.ndjson\")")
            fn = re.findall(r"^def (test_\w+)", test_src[:at], re.M)[-1]
            if want not in fn:
                raise SystemExit(f"{meta['id']}: sample_{kind}.ndjson is no longer recorded by a {want} test ({fn})")
            replays[kind]["from"] = want
        if replays["attack"]["alerts"] < 1 or replays["benign"]["alerts"] != 0:
            raise SystemExit(f"{meta['id']}: replay results are not 'attack alerts, benign does not'")
        still = test_src.count(STILL_VISIBLE)
        if still < 1:
            raise SystemExit(f"{meta['id']}: the fixed-service test no longer asserts that the rule still fires")

        # versions
        codes, versions_out = {}, []
        for v in ("vulnerable", "fixed"):
            codes[v] = read(lab / v / "app.py")
        for v in ("vulnerable", "fixed"):
            text, status = sh([sinkline_cli, "scan", v, "--no-color"], lab, ok=(0, 1))
            repo_text = read(lab / "sinkline" / f"{v}.txt")
            # The files recorded in the repository were written on Windows and hold the tree glyphs (the box-drawing
            # characters of the path) as mojibake, UTF-8 read as cp1252 and encoded again. Undo that before comparing, so the
            # page shows the glyphs the tool really prints.
            try:
                repo_text = repo_text.encode("cp1252").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            if repo_text != f"$ sinkline scan {v} --no-color\n{text}":
                raise SystemExit(f"{meta['id']}/{v}: fresh sinkline output differs from the file recorded in the repository")
            raw, _ = sh([sinkline_cli, "scan", v, "--no-color", "--format", "json"], lab, ok=(0, 1))
            rep = json.loads(raw)
            findings = [{"rule_id": f["rule_id"], "cwe": f["cwe"], "severity": f["severity"], "file": f["file"], "line": f["line"],
                         "flow": [{"kind": s["kind"], "line": s["line"]} for s in f["flow"]]} for f in rep["findings"]]
            if rep["errors"]:
                raise SystemExit(f"{meta['id']}/{v}: sinkline reported errors {rep['errors']}")
            if v == "vulnerable":
                reading = "true positive" if findings else "missed"
            else:
                reading = "false positive" if findings else "clean"
            lines = codes[v].splitlines()
            marks = {"bug": [], "changed": changed_lines(codes["vulnerable"], codes[v]) if v == "fixed" else []}
            if v == "vulnerable":
                if meta["bug_text"] not in lines[meta["bug"] - 1] or meta["bug_readme"] not in readme:
                    raise SystemExit(f"{meta['id']}: the bug line {meta['bug']} no longer matches the source and the README")
                marks["bug"] = [meta["bug"]]
            versions_out.append({
                "id": v, "label": "Vulnerable" if v == "vulnerable" else "Fixed",
                "summary": meta[v], "outcome": meta["impact"] if v == "vulnerable" else meta["blocked"],
                "file": f"labs/{meta['id']}/{v}/app.py", "code": codes[v], "marks": marks,
                "tests": by_version[v],
                "sinkline": {"command": f"sinkline scan {v} --no-color", "status": status, "out": text, "findings": findings,
                             "reading": reading, "note": meta["sinkline_note"].get(v, "")},
            })
        labs.append({
            "id": meta["id"], "n": meta["n"], "title": meta["title"], "cwe": meta["cwe"],
            "readme": f"labs/{meta['id']}/README.md",
            "versions": versions_out,
            "detection": {"rule": str(rule.relative_to(clone)).replace("\\", "/"), "titles": titles, "correlation": corr,
                          "test": detect, "attack": replays["attack"], "benign": replays["benign"],
                          "fixed_still_alerts": True},
        })

    lab_total = sum(r["passed"] for l in labs for v in l["versions"] for r in v["tests"]) + sum(l["detection"]["test"]["passed"] for l in labs)
    if lab_total + safety != passed:
        raise SystemExit(f"test counts do not add up: labs {lab_total} + safety {safety} != {passed}")
    return {
        "roles": ROLES,
        "provenance": {
            "tool": "vulnlab", "version": TAG.lstrip("v"), "tag": TAG, "commit": COMMIT[:7], "commit_full": COMMIT,
            "repo": REPO_URL, "ci_run": CI_RUN, "captured": CAPTURED, **versions,
            "os": sh([py, "-c", "import platform;print(platform.system()+' '+platform.release())"])[0].strip(),
            "commands": {
                "tests": "python -m pytest -v -p no:cacheprovider",
                "sinkline": "sinkline scan VARIANT --no-color (run from the lab directory)",
                "replay": "python -m vulnlab_common.replay RULE LOG",
            },
            "totals": {"passed": passed, "lab_tests": lab_total, "safety_tests": safety},
            "repo_checks": {"sinkline_check": "exit 0 (tools/sinkline_check.py)", "sigma_check": "0 errors, 0 condition errors, 0 issues"},
        },
        "labs": labs,
    }


def comparable(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    for k in ("captured", "python", "os"):
        d["provenance"].pop(k, None)
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone", help="an existing clone of vulnlab at the tag (default: clone into a scratch directory)")
    ap.add_argument("--venv", help="an existing virtual environment with requirements.lock installed (default: create one)")
    ap.add_argument("--repo", default=REPO_URL, help="URL or local path to clone from")
    ap.add_argument("--check", action="store_true", help="compare with the stored file, write nothing")
    a = ap.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"run this script with Python 3.12 (it builds the venv from the running interpreter), got {sys.version.split()[0]}")
    tmp = Path(tempfile.mkdtemp(prefix="vulnlab-bench-"))
    try:
        clone = Path(a.clone) if a.clone else tmp / "vulnlab"
        if not a.clone:
            sh(["git", "clone", "--quiet", a.repo, str(clone)])
        sh(["git", "checkout", "--quiet", TAG], clone)
        venv = Path(a.venv) if a.venv else tmp / "venv"
        if not a.venv:
            sh([sys.executable, "-m", "venv", str(venv)])
            sh([venv_bin(venv, "python"), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", "requirements.lock"], clone)
            sh([venv_bin(venv, "python"), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-deps", "-e", "."], clone)
        fresh = build(clone, venv)
        pv = fresh["provenance"]
        print(f"vulnlab {pv['tag']} commit {pv['commit_full']}")
        print(f"python {pv['python']}, pytest {pv['pytest']}, sinkline {pv['sinkline']}, tripline {pv['tripline']}, pySigma {pv['pysigma']}, {pv['os']}")
        print(f"{pv['totals']['passed']} passed ({pv['totals']['lab_tests']} in the labs, {pv['totals']['safety_tests']} safety and harness)")
        if not a.check:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(fresh, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            print(f"wrote {OUT.relative_to(ROOT)}")
            return 0
        if not OUT.exists():
            print(f"FAIL missing {OUT.name}")
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        ok = comparable(stored) == comparable(fresh)
        if not ok:
            a_, b_ = json.dumps(comparable(stored), indent=1).splitlines(), json.dumps(comparable(fresh), indent=1).splitlines()
            for line in list(difflib.unified_diff(a_, b_, "stored", "fresh", lineterm="", n=1))[:40]:
                print(line)
        print(f"checked {OUT.name} against a fresh run of vulnlab {TAG}: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
