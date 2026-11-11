#!/usr/bin/env python3
"""Capture or verify the real kevgate-admit responses shown by the Admission desk bench.

  python scripts/capture_admission_bench.py [--go PATH_TO_GO] [--repo URL_OR_PATH]            # capture, write the data files
  python scripts/capture_admission_bench.py [--go PATH_TO_GO] [--repo URL_OR_PATH] --check    # capture again, compare, write nothing

What it does, every time (nothing is cached and nothing is edited by hand):

  1. clones the repository at the tag (default: kevgate-admit v0.1.0) into a temporary directory and checks that the
     tag points at the expected commit;
  2. builds the real binary with `go build ./cmd/kevgate-admit` and prints the commit and the Go version used;
  3. starts `kevgate-admit serve --self-signed` with the demo policy, the demo KEV subset and the demo reports from
     `deploy/demo/`, and POSTs one AdmissionReview v1 request per image and namespace over TLS (the same request that
     `TestDemoScenarios` in internal/app/app_test.go builds);
  4. starts a second instance with `--evidence-public-key-file` and a policy with `requireSignedEvidence: true`, signs the
     demo reports with `kevgate-admit keygen` and `sign-report`, and POSTs the requests again with the reports signed,
     edited after signing, and unsigned;
  5. runs the real Trivy parser (`internal/trivy.Parse`) and the real scorer (`internal/risk.Score`) over the trimmed real
     Trivy 0.76.2 report in `internal/trivy/testdata/`, through a 30-line Go program placed in the temporary clone;
  6. checks that every Go identifier the page names for the evidence lookup path exists in the clone;
  7. writes

       assets/data/admission-bench.json         the raw AdmissionReview responses and what the page needs to show them
       assets/data/admission-bench-readme.json  the README's transcript blocks at the tag (test data, not loaded by the page)

     Only the response bodies, the parsed Trivy report and the README text come from the tool; the script adds the
     labels, and extracts the rule names and finding lines from the message text so the page can show a table.

--check exits 1 if a fresh run differs from the stored files (the Go version, the date and the temporary paths are
provenance and are not compared). The signatures are random per run; only the resulting decisions are stored.
"""
from __future__ import annotations

import argparse
import datetime
import http.client
import json
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "admission-bench.json"
OUT_README = ROOT / "assets" / "data" / "admission-bench-readme.json"

REPO_URL = "https://github.com/samiali38183/kevgate-admit"
TAG = "v0.1.0"
COMMIT = "161169a9cfbe2dff888acec1d3303bc702dc2587"

D_CLEAN = "sha256:" + "1" * 64
D_KEV = "sha256:" + "2" * 64
D_OVER = "sha256:" + "3" * 64
BASE = "registry.example.com/demo/"

IMAGES = [
    {"id": "clean", "label": "clean", "ref": f"{BASE}clean@{D_CLEAN}",
     "what": "Digest-pinned; the report lists three low and medium findings, none in KEV."},
    {"id": "kev", "label": "kev-vulnerable", "ref": f"{BASE}kev-vulnerable@{D_KEV}",
     "what": "Digest-pinned; the report lists CVE-2021-44228, which the demo KEV subset contains."},
    {"id": "over", "label": "over-threshold", "ref": f"{BASE}over-threshold@{D_OVER}",
     "what": "Digest-pinned; no KEV finding, but CVE-2099-10004 scores above 40 (CVSS 9.8, EPSS 0.9)."},
    {"id": "tag", "label": "tag-only", "ref": f"{BASE}clean:latest",
     "what": "A tag, no digest. The webhook never resolves tags."},
    {"id": "evil", "label": "malformed reference", "ref": "ghcr.io/org/../evil",
     "what": "A path with a dot segment. Earlier builds accepted it; the strict OCI-grammar parser rejects it."},
]
POLICIES = [
    {"id": "enforce", "namespace": "demo-enforce", "scope": "demo-enforce", "label": "demo-enforce",
     "summary": "mode enforce; denyKev, maxRisk 40, requireDigest, requireEvidence deny, registry registry.example.com/demo only"},
    {"id": "audit", "namespace": "demo-audit", "scope": "demo-audit", "label": "demo-audit",
     "summary": "same rules, mode audit: the request is admitted and the would-be denials come back as warnings"},
    {"id": "default", "namespace": "other", "scope": "_default", "label": "any other namespace",
     "summary": "the policy's default rule: denyKev, requireDigest, requireEvidence deny; no maxRisk, no registry list"},
]
# The policy used in the repository's TestServeWithSignedEvidence (internal/app/sign_test.go), applied to one namespace.
SIGNED_POLICY = """version: 1
default:
  requireDigest: true
  requireEvidence: deny
  denyKev: true
  maxRisk: 40
  requireSignedEvidence: true
"""
SIGNED_NS = "demo-signed"
# State name -> (label, how the report store was changed). The tamper edit renames one finding in the signed file.
SIGNED_STATES = [
    {"id": "valid", "label": "Valid signature", "edit": "Every report signed with sign-report; nothing changed."},
    {"id": "tampered", "label": "Report edited after signing", "edit": "One CVE id in the report renamed after it was signed (the signature file is untouched)."},
    {"id": "missing", "label": "Signature missing", "edit": "The .sig files are absent; the report itself is unchanged."},
]
TAMPER = {D_CLEAN: ("CVE-2099-10002", "CVE-2099-00000"), D_KEV: ("CVE-2021-44228", "CVE-2021-00000"),
          D_OVER: ("CVE-2099-10004", "CVE-2099-00000")}

# Go functions the page's "evidence lookup path" cites, each as (file, function or method name) that must exist at the tag.
NAMES = [
    ("internal/admission/handler.go", "Review"), ("internal/admission/handler.go", "resolve"),
    ("internal/admission/handler.go", "lookupBounded"), ("internal/admission/decode.go", "Extract"),
    ("internal/imageref/imageref.go", "Parse"), ("internal/imageref/imageref.go", "Pinned"),
    ("internal/evidence/evidence.go", "FileName"), ("internal/evidence/evidence.go", "Lookup"),
    ("internal/evidence/evidence.go", "checkSignature"), ("internal/evsign/evsign.go", "Verify"),
    ("internal/trivy/trivy.go", "ParseReader"), ("internal/risk/risk.go", "Score"),
    ("internal/policy/policy.go", "RuleFor"), ("internal/policy/eval.go", "Evaluate"),
    ("internal/policy/eval.go", "findings"), ("internal/policy/eval.go", "Message"),
    ("internal/policy/eval.go", "ResponseWarnings"),
]

DUMP_GO = """package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/samiali38183/kevgate-admit/internal/risk"
	"github.com/samiali38183/kevgate-admit/internal/trivy"
)

type row struct {
	ID, Package, Installed, Fixed, Severity string
	CVSS                                    float64
	EPSS                                    *float64
	Risk                                    float64
}

func main() {
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	rep, err := trivy.Parse(data)
	if err != nil {
		panic(err)
	}
	var rows []row
	for _, f := range rep.Findings {
		var e *float64
		if f.HasEPSS {
			v := f.EPSS
			e = &v
		}
		r, err := risk.Score(f.CVSS, f.EPSS, 4, false)
		if err != nil {
			panic(err)
		}
		rows = append(rows, row{f.ID, f.Package, f.Installed, f.Fixed, f.Severity, f.CVSS, e, r})
	}
	out := map[string]any{"artifact": rep.ArtifactName, "created": rep.CreatedAt.Format("2006-01-02T15:04:05Z"),
		"digests": rep.Digests, "skipped": rep.Skipped, "findings": rows}
	b, _ := json.Marshal(out)
	fmt.Println(string(b))
}
"""


def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if p.returncode != 0:
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p.stdout.strip()


def find_go(arg: str | None) -> str:
    g = arg or shutil.which("go")
    if not g:
        raise SystemExit("Go not found: pass --go PATH_TO_GO (the tag needs Go 1.27.4 or newer)")
    return g


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Server:
    """One `kevgate-admit serve --self-signed` process and a TLS client that trusts its throw-away CA."""

    def __init__(self, binary: Path, work: Path, name: str, args: list[str]) -> None:
        self.port, self.mport = free_port(), free_port()
        self.ca = work / f"{name}-ca.pem"
        self.log = open(work / f"{name}.log", "w+b")
        self.proc = subprocess.Popen(
            [str(binary), "serve", "--listen", f"127.0.0.1:{self.port}", "--metrics-listen", f"127.0.0.1:{self.mport}",
             "--self-signed", "--self-signed-hosts", "localhost,127.0.0.1", "--self-signed-ca-out", str(self.ca),
             "--reload-interval", "50ms"] + args, stdout=self.log, stderr=self.log)
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise SystemExit("kevgate-admit exited early:\n" + self.logtext())
            if self.ca.exists() and self.ca.stat().st_size > 0:
                try:
                    socket.create_connection(("127.0.0.1", self.port), 0.5).close()
                    break
                except OSError:
                    pass
            time.sleep(0.1)
        else:
            raise SystemExit("kevgate-admit did not start:\n" + self.logtext())
        self.ctx = ssl.create_default_context(cafile=str(self.ca))

    def logtext(self) -> str:
        self.log.flush()
        self.log.seek(0)
        return self.log.read().decode("utf-8", "replace")

    def post(self, body: str) -> dict:
        conn = http.client.HTTPSConnection("127.0.0.1", self.port, context=self.ctx, timeout=10)
        conn.request("POST", "/validate", body=body.encode("utf-8"), headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        data = r.read()
        conn.close()
        if r.status != 200:
            raise SystemExit(f"HTTP {r.status}: {data!r}")
        return json.loads(data)

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def review(ns: str, image: str) -> str:
    """The request TestDemoScenarios builds: a Deployment with one container."""
    obj = json.dumps({"metadata": {"name": "web"}, "spec": {"template": {"spec": {"containers": [{"name": "web", "image": image}]}}}},
                     separators=(",", ":"))
    return ('{"apiVersion":"admission.k8s.io/v1","kind":"AdmissionReview","request":{"uid":"u1","kind":{"group":"apps","version":"v1",'
            '"kind":"Deployment"},"resource":{"group":"apps","version":"v1","resource":"deployments"},"operation":"CREATE","namespace":'
            + json.dumps(ns) + ',"object":' + obj + "}}")


RULE_RE = re.compile(r"^- \[(\w+)\] ", re.M)
WARN_RE = re.compile(r"would deny \[(\w+)\]")
FIND_RE = re.compile(r"^    (CVE-[\w-]+|GHSA-[\w-]+)\s+(KEV\s)?\s*risk\s+([\d.]+)(?:\s+(.*))?$")


def analyse(raw: dict) -> dict:
    """Decision, rules and finding lines, read back out of the response text."""
    r = raw["response"]
    msg = (r.get("status") or {}).get("message", "")
    warns = r.get("warnings") or []
    decision = "denied" if not r["allowed"] else ("warned" if warns else "allowed")
    rules = RULE_RE.findall(msg) if msg else [m for w in warns for m in WARN_RE.findall(w)]
    findings = []
    rule = None
    image = None
    for line in msg.splitlines():
        m = re.match(r"^- \[(\w+)\] (\S+): ", line)
        if m:
            rule, image = m.group(1), m.group(2)
            continue
        f = FIND_RE.match(line)
        if f and rule:
            findings.append({"rule": rule, "image": image, "cve": f.group(1), "kev": bool(f.group(2)),
                             "risk": float(f.group(3)), "pkg": (f.group(4) or "").strip()})
    return {"decision": decision, "rules": rules, "findings": findings}


def worked(repo_reports: Path, digest: str, cve: str, risk: float) -> str:
    """The formula with the report's numbers substituted. Recomputed here and required to equal the webhook's own number."""
    rep = json.loads((repo_reports / f"sha256-{digest.split(':')[1]}.json").read_text(encoding="utf-8"))
    for res in rep["Results"]:
        for v in res["Vulnerabilities"]:
            if v["VulnerabilityID"] == cve:
                cvss = max(c.get("V3Score", 0) for c in v["CVSS"].values())
                epss = v.get("EPSS", 0)
                kev = 1 if cve == "CVE-2021-44228" else 0
                acr = 4
                val = 100 * (0.40 * kev + 0.25 * acr / 8 + 0.20 * epss + 0.20 * cvss / 10) / 1.05
                if round(val, 1) != risk:
                    raise SystemExit(f"risk for {cve}: webhook says {risk}, formula gives {val}")
                return (f"100 * (0.40*{kev} + 0.25*{acr}/8 + 0.20*{epss:g} + 0.20*{cvss:g}/10) / 1.05 = {risk}")
    raise SystemExit(f"{cve} not in report")


def readme_blocks(readme: str) -> list[str]:
    """Fenced blocks between 'Examples from the test suite' and 'Configuration' (examples and both transcripts)."""
    a = readme.index("## Examples from the test suite")
    b = readme.index("## Configuration")
    return [m.group(1).rstrip("\n") for m in re.finditer(r"```[a-z]*\n(.*?)```", readme[a:b], re.S)]


def capture(go: str, repo: str) -> tuple[dict, dict]:
    tmp = Path(tempfile.mkdtemp(prefix="admit-bench-"))
    srv: list[Server] = []
    try:
        clone = tmp / "kevgate-admit"
        sh(["git", "clone", "--quiet", "--branch", TAG, "--depth", "1", repo, str(clone)])
        commit = sh(["git", "rev-parse", "HEAD"], clone)
        if commit != COMMIT:
            raise SystemExit(f"tag {TAG} is {commit}, expected {COMMIT}")
        goversion = sh([go, "version"])
        binary = tmp / ("kevgate-admit.exe" if sys.platform == "win32" else "kevgate-admit")
        sh([go, "build", "-o", str(binary), "./cmd/kevgate-admit"], clone)
        version = sh([str(binary), "version"])
        print(f"commit {commit} ({TAG}); {goversion}; binary reports: {version}", file=sys.stderr)

        demo = clone / "deploy" / "demo"
        common = ["--policy-file", str(demo / "policy.yaml"), "--kev-file", str(demo / "kev-demo.json")]
        s1 = Server(binary, tmp, "demo", common + ["--evidence-dir", str(demo / "reports")])
        srv.append(s1)
        results = []
        for pol in POLICIES:
            for img in IMAGES:
                raw = s1.post(review(pol["namespace"], img["ref"]))
                a = analyse(raw)
                results.append({"image": img["id"], "policy": pol["id"], "raw": raw, **a})
        s1.stop()
        srv.remove(s1)

        # worked risk figures for the findings that appear in a denial text
        digest_of = {"kev": D_KEV, "over": D_OVER}
        for r in results:
            for f in r["findings"]:
                f["worked"] = worked(demo / "reports", digest_of[r["image"]], f["cve"], f["risk"])

        # signed evidence
        rep_dir = tmp / "reports"
        shutil.copytree(demo / "reports", rep_dir)
        keys = tmp / "keys"
        keys.mkdir()
        priv, pub = keys / "report-key.pem", keys / "report-key.pub.pem"
        sh([str(binary), "keygen", "-type", "ed25519", "-private-out", str(priv), "-public-out", str(pub)])
        files = {d: rep_dir / f"sha256-{d.split(':')[1]}.json" for d in (D_CLEAN, D_KEV, D_OVER)}
        sh([str(binary), "sign-report", "-key", str(priv)] + [str(p) for p in files.values()])
        sig_files = {d: p.with_name(p.name + ".sig") for d, p in files.items()}
        for p in sig_files.values():
            if not p.exists():
                raise SystemExit(f"sign-report did not write {p.name}")
        # the policy text must be the repository's own test policy
        sign_test = (clone / "internal" / "app" / "sign_test.go").read_text(encoding="utf-8")
        if "const signedPolicy = `" + SIGNED_POLICY + "`" not in sign_test:
            raise SystemExit("SIGNED_POLICY differs from signedPolicy in internal/app/sign_test.go")
        pol_file = tmp / "signed-policy.yaml"
        pol_file.write_text(SIGNED_POLICY, encoding="utf-8", newline="\n")
        s2 = Server(binary, tmp, "signed", ["--policy-file", str(pol_file), "--kev-file", str(demo / "kev-demo.json"),
                                            "--evidence-dir", str(rep_dir), "--evidence-public-key-file", str(pub)])
        srv.append(s2)
        sref = {"clean": D_CLEAN, "kev": D_KEV, "over": D_OVER}
        names = {"clean": "clean", "kev": "kev-vulnerable", "over": "over-threshold"}
        sresults = []
        originals = {d: p.read_bytes() for d, p in files.items()}
        for st in SIGNED_STATES:
            for d, p in files.items():  # reset
                p.write_bytes(originals[d])
                if not sig_files[d].exists():
                    raise SystemExit("signature file lost")
            if st["id"] == "tampered":
                for d, p in files.items():
                    old, new = TAMPER[d]
                    text = originals[d].decode("utf-8")
                    if text.count(old) != 1:
                        raise SystemExit(f"tamper marker {old} occurs {text.count(old)} times")
                    p.write_bytes(text.replace(old, new).encode("utf-8"))
            sig_backup = {d: sig_files[d].read_bytes() for d in sig_files}
            if st["id"] == "missing":
                for p in sig_files.values():
                    p.unlink()
            for iid, d in sref.items():
                raw = s2.post(review(SIGNED_NS, f"{BASE}{names[iid]}@{d}"))
                sresults.append({"image": iid, "state": st["id"], "raw": raw, **analyse(raw)})
            for d, b in sig_backup.items():
                sig_files[d].write_bytes(b)
        s2.stop()
        srv.remove(s2)
        for r in sresults:
            for f in r["findings"]:
                if r["image"] in digest_of and r["state"] == "valid":
                    f["worked"] = worked(demo / "reports", digest_of[r["image"]], f["cve"], f["risk"])

        # the real Trivy fixture through the real parser and scorer
        fixture = clone / "internal" / "trivy" / "testdata" / "real-trivy-0.76.2-python-3.9-slim-bullseye.json"
        dump_dir = clone / "cmd" / "zz-dump"
        dump_dir.mkdir()
        (dump_dir / "main.go").write_text(DUMP_GO, encoding="utf-8", newline="\n")
        parsed = json.loads(sh([go, "run", "./cmd/zz-dump", str(fixture)], clone))
        raw_fixture = json.loads(fixture.read_text(encoding="utf-8"))
        entries = [v for r in raw_fixture["Results"] for v in r.get("Vulnerabilities", [])]
        if len(entries) != len(parsed["findings"]):
            raise SystemExit("fixture entries and parsed findings differ in number")
        sevs = {v["VulnerabilityID"]: v["Title"] for v in entries}
        for f in parsed["findings"]:
            f["title"] = sevs[f["ID"]]
        scanner = {
            "fixture": "internal/trivy/testdata/real-trivy-0.76.2-python-3.9-slim-bullseye.json",
            "bytes": fixture.stat().st_size,
            "trivy": "0.76.2",
            "target": raw_fixture["Results"][0]["Target"],
            "raw_entries": len(entries),
            "parser": parsed,
            "scored_with": "risk.Score(cvss, epss, acr 4, kev false): no EPSS file, no KEV match, as under the demo policy",
        }

        # names cited on the page
        for rel, fn in NAMES:
            if not re.search(r"^func (\([^)]*\) )?" + fn + r"\(", (clone / rel).read_text(encoding="utf-8"), re.M):
                raise SystemExit(f"{rel} has no function {fn}")
        readme = (clone / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        blocks = readme_blocks(readme)
        alltext = "\n".join(blocks)
        for r in results + sresults:
            msg = (r["raw"]["response"].get("status") or {}).get("message", "")
            warns = r["raw"]["response"].get("warnings") or []
            parts = [msg] if msg else []
            parts += warns
            r["in_readme"] = all(p in alltext for p in parts) if parts else None

        fm = re.search(r"`(risk = 100 \* [^`]+)`", readme)
        if not fm:
            raise SystemExit("risk formula not found in the README")
        data = {
            "provenance": {
                "tool": "kevgate-admit", "tag": TAG, "commit": commit, "repo": REPO_URL, "binary": version,
                "go": goversion, "captured": datetime.date.today().isoformat(),
                "command": "kevgate-admit serve --self-signed --policy-file deploy/demo/policy.yaml --kev-file deploy/demo/kev-demo.json --evidence-dir deploy/demo/reports",
                "command_signed": "kevgate-admit serve --self-signed --policy-file signed-policy.yaml --kev-file deploy/demo/kev-demo.json --evidence-dir SIGNED_REPORTS --evidence-public-key-file report-key.pub.pem",
                "regenerate": "python scripts/capture_admission_bench.py",
                "label": "Synthetic demo data and test output from a locally run webhook, not a cluster run.",
                "request": review("NAMESPACE", "IMAGE"),
                "names_verified": [f"{rel}: {fn}" for rel, fn in NAMES], "formula": fm.group(1),
            },
            "images": IMAGES, "policies": POLICIES, "results": results,
            "signed": {"policy": SIGNED_POLICY, "namespace": SIGNED_NS, "scope": "_default", "key": "ed25519", "states": SIGNED_STATES,
                       "images": ["clean", "kev", "over"], "results": sresults},
            "scanner": scanner,
        }
        return data, {"tag": TAG, "commit": commit, "blocks": blocks}
    finally:
        for s in srv:
            s.stop()
        shutil.rmtree(tmp, ignore_errors=True)


def comparable(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    d.get("provenance", {}).pop("go", None)
    d.get("provenance", {}).pop("captured", None)
    return d


def dumps(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", help="path to the go executable (default: PATH)")
    ap.add_argument("--repo", default=REPO_URL, help="URL or local path of the kevgate-admit repository (default: GitHub)")
    ap.add_argument("--check", action="store_true", help="compare with the stored files, write nothing")
    a = ap.parse_args()
    data, readme = capture(find_go(a.go), a.repo)
    n = len(data["results"]) + len(data["signed"]["results"])
    if not a.check:
        OUT.write_text(dumps(data), encoding="utf-8", newline="\n")
        OUT_README.write_text(dumps(readme), encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT)} ({n} responses) and {OUT_README.relative_to(ROOT)}")
        return 0
    problems = []
    for path, fresh in ((OUT, data), (OUT_README, readme)):
        if not path.exists():
            problems.append(f"missing {path.name}")
        elif comparable(json.loads(path.read_text(encoding="utf-8"))) != comparable(fresh):
            problems.append(f"{path.name} differs from a fresh run")
    for p in problems:
        print("FAIL", p)
    print(f"checked {n} responses and the README blocks against a fresh run of {data['provenance']['tag']}: {'OK' if not problems else 'FAILED'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
