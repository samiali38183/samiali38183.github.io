#!/usr/bin/env python3
"""Capture or verify the data behind the "Control to evidence matrix" bench on the kevgate page.

  python scripts/capture_kevgate_bench.py                       # clone, install, collect, write the data
  python scripts/capture_kevgate_bench.py --check               # same, compare with the stored file, change nothing
  python scripts/capture_kevgate_bench.py --clone DIR --venv DIR [--check]   # reuse a clone at the tag and a venv

What it does (needs git, Python 3.12, the gh CLI and network access to GitHub and ghcr.io):
  1. Clones https://github.com/samiali38183/kevgate into a scratch directory, checks out v0.1.1 and refuses to continue if the
     commit is not the one recorded below. The public repository is never modified.
  2. Creates a virtual environment, installs the project with its dev extras and runs `pytest --collect-only`. Every cited test is
     resolved to a real collected test (and its number of parametrized cases) and then run, so a name that does not exist or a
     test that fails stops the script.
  3. Locates every cited source range by searching the code at the tag: a start pattern that must match exactly once, and an end
     (the rest of the indented block, a closing brace, or a pattern). Line numbers are never typed in by hand.
  4. Reads the threat and the residual risk of each control from docs/THREAT_MODEL.md (the table row whose threat cell contains the
     given text) or, where that file has no row, quotes the sentence from the doc named in the spec. A quote that is not found
     verbatim stops the script.
  5. Resolves each cited CI step from `gh api repos/samiali38183/kevgate/actions/runs/<id>/jobs` (job name, job id, step number,
     conclusion) and finds the step in the workflow file at the tag. The runs are pinned in RUNS below: the latest runs on main
     for ci, security and deploy-kind (the tag commit), the latest terraform run on main (the commit before the version bump;
     the script checks that infra/ and the workflow did not change between that commit and the tag) and the release run.
  6. Reads the release image from ghcr.io with the anonymous token endpoint: the digest of tag 0.1.1 and the attestation
     artifacts attached to it (SBOM, signature, provenance).
  7. Writes assets/data/kevgate-bench.json and prints the commit and the tool versions it used.

--check exits 1 if the stored file differs from a fresh capture (the date and the Python, pytest and OS strings are provenance
and are not compared).
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "kevgate-bench.json"

OWNER_REPO = "samiali38183/kevgate"
REPO_URL = f"https://github.com/{OWNER_REPO}"
TAG = "v0.1.1"
COMMIT = "973c8c143e8e7d571e52af3f290f4c835954599a"
CAPTURED = "2026-11-11"
IMAGE = "ghcr.io/samiali38183/kevgate"
IMAGE_TAG = "0.1.1"

# workflow -> run id. ci, security and deploy-kind are the push runs on main for the tag commit; terraform has a path filter, so
# its latest run on main is the one for the previous commit; release is the run for the tag.
RUNS = {
    "ci": 42960808156,
    "security": 42960808037,
    "deploy-kind": 42960807983,
    "terraform": 42956666367,
    "release": 42960813836,
}
TERRAFORM_RUN_SHA = "b08a920d25d0003c2c7c6624770c0cee3315d8b4"

LAYERS = [
    {"id": "application", "label": "Application"},
    {"id": "container", "label": "Container"},
    {"id": "cluster", "label": "Cluster"},
    {"id": "cloud", "label": "Cloud"},
    {"id": "supply", "label": "Supply chain"},
]

PY312 = "lint, types, tests (py3.12)"


# ---------------------------------------------------------------------------------------------------------------------
# Specs. R(path, start_regex, end): `end` is None (the rest of the indented block), "one" (the start line only), "brace"
# (up to the closing brace at the same indent), "eof", or a regex (first match at or after the start line, inclusive).
# ---------------------------------------------------------------------------------------------------------------------
def R(path: str, start: str, end: str | None = None) -> dict:
    return {"path": path, "start": start, "end": end}


APP, SRC = "src/kevgate/app.py", "src/kevgate"
T_AUTH = "tests/test_auth.py"
T_FAIL = "tests/test_auth_failures.py"
T_API = "tests/test_api.py"
T_MUT = "tests/test_mutation_kills.py"
T_RATE = "tests/test_ratelimit.py"
T_READY = "tests/test_readiness.py"
T_CFG = "tests/test_config_cli_logs.py"


def tm(threat: str, limit_cols: tuple[str, ...] = ("residual",)) -> dict:
    return {"kind": "tm", "match": threat, "cols": limit_cols}


def quote(doc: str, start: str, end: str) -> dict:
    return {"kind": "quote", "doc": doc, "start": start, "end": end}


def ci(wf: str, job: str | None, step: str, asserts: list[dict] | None = None) -> dict:
    return {"wf": wf, "job": job, "step": step, "asserts": asserts or []}


CONTROLS: list[dict] = [
    {
        "id": "keys", "layer": "application", "title": "API keys stored as hashes and compared in constant time",
        "threat": tm("Timing side channel reveals key bytes or which key matched"),
        "limits": [tm("Key file or a backup leaks")],
        "code": [R(SRC + "/auth.py", r"^def generate_key\("), R(SRC + "/auth.py", r"^    def authenticate\(")],
        "tests": [f"{T_AUTH}::test_authenticate_checks_every_key",
                  f"{T_MUT}::test_authenticate_compares_every_key_with_compare_digest",
                  f"{T_AUTH}::test_generated_keys_are_unique_and_high_entropy"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "scopes", "layer": "application", "title": "401 for no or unknown key, 403 for a key without the scope",
        "threat": tm("A read or write key performs admin actions"),
        "limits": [tm("A read or write key performs admin actions"), tm("Caller pretends to be a scanner or admin")],
        "code": [R(APP, r"^def require\("), R(SRC + "/auth.py", r"^    def allows\(")],
        "tests": [f"{T_API}::test_no_key_is_401_with_challenge", f"{T_API}::test_bad_key_is_401",
                  f"{T_API}::test_scope_matrix", f"{T_API}::test_admin_scope_implies_everything"],
        "ci": [ci("ci", PY312, "pytest with coverage"),
               ci("deploy-kind", None, "Smoke test through port-forward",
                  [R("deploy/smoke.sh", r'status GET /queue\)" == 401', r'ok "GET /queue with wrong key -> 401"')])],
    },
    {
        "id": "failures", "layer": "application", "title": "Failed authentications throttled per source address before any key is checked",
        "threat": tm("Brute-forcing a key or key id"),
        "limits": [tm("Brute-forcing a key or key id")],
        "code": [R(APP, r"# Before any credential check", r"^                \)$"), R(SRC + "/ratelimit.py", r"^    def peek\("),
                 R(SRC + "/ratelimit.py", r"^    def charge\("), R(SRC + "/clientip.py", r"^def resolve_client_address\(")],
        "tests": [f"{T_FAIL}::test_repeated_bad_keys_get_throttled_before_auth",
                  f"{T_FAIL}::test_valid_requests_never_consume_failure_budget",
                  f"{T_FAIL}::test_peek_does_not_spend_tokens",
                  f"{T_FAIL}::test_trusted_proxy_header_separates_sources",
                  f"{T_FAIL}::test_forwarded_for_ignored_when_peer_not_trusted",
                  f"{T_FAIL}::test_resolve_client_address"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "bucket", "layer": "application", "title": "Per-key token-bucket rate limit with Retry-After",
        "threat": tm("One client floods the API"),
        "limits": [tm("One client floods the API")],
        "code": [R(SRC + "/ratelimit.py", r"^class TokenBucketLimiter"), R(APP, r"decision = st\.limiter\.acquire\(bucket\)", r"^            \)$")],
        "tests": [f"{T_RATE}::test_burst_then_block_then_refill", f"{T_RATE}::test_retry_after_reflects_refill_rate",
                  f"{T_API}::test_rate_limit_returns_429_with_retry_after", f"{T_API}::test_ops_endpoints_not_rate_limited"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "body", "layer": "application", "title": "Request body size limit on declared length and on streamed chunks",
        "threat": tm("Large or slow bodies exhaust memory"),
        "limits": [tm("Large or slow bodies exhaust memory")],
        "code": [R(SRC + "/middleware.py", r"^class BodySizeLimitMiddleware"), R(APP, r"app\.add_middleware\(BodySizeLimitMiddleware", "one")],
        "tests": [f"{T_API}::test_body_over_limit_by_content_length_is_413", f"{T_API}::test_chunked_body_over_limit_is_413",
                  f"{T_MUT}::test_many_small_chunks_over_limit_is_413", f"{T_MUT}::test_chunks_under_limit_pass_through"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "headers", "layer": "application", "title": "Security response headers on every response",
        "threat": tm("Browser or proxy caches findings"),
        "limits": [tm("Browser or proxy caches findings")],
        "code": [R(SRC + "/middleware.py", r"^SECURITY_HEADERS", r"^\}$"),
                 R(SRC + "/middleware.py", r"for name, value in SECURITY_HEADERS\.items\(\):", r"headers\[name\] = value")],
        "tests": [f"{T_API}::test_security_headers_on_api_responses"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "logs", "layer": "application", "title": "JSON logs that carry a key id and never the key",
        "threat": tm("Keys end up in logs"),
        "limits": [tm("Keys end up in logs")],
        "code": [R(SRC + "/middleware.py", r"^            logger\.info\($", r"^            \)$"), R(APP, r"^def _log_auth_failure\("),
                 R(SRC + "/logs.py", r"^class JsonFormatter")],
        "tests": [f"{T_API}::test_access_log_has_fields_and_no_secrets", f"{T_FAIL}::test_failures_log_client_address_and_never_the_key",
                  f"{T_CFG}::test_json_formatter_shape"],
        "ci": [ci("ci", PY312, "pytest with coverage")],
    },
    {
        "id": "ready", "layer": "application", "title": "Readiness checks storage headroom, a rolled-back write and database integrity",
        "threat": tm("Disk fills or file is locked"),
        "limits": [tm("Disk fills or file is locked")],
        "code": [R(APP, r'^    def readyz\(', None), R(SRC + "/db.py", r"^    def storage_ok\("), R(SRC + "/db.py", r"^    def write_probe\("),
                 R(SRC + "/db.py", r"^    def integrity_ok\(")],
        "tests": [f"{T_READY}::test_write_probe_fails_when_another_connection_holds_the_write_lock",
                  f"{T_READY}::test_storage_fails_when_disk_nearly_full", f"{T_READY}::test_integrity_detects_corruption",
                  f"{T_READY}::test_integrity_over_budget_is_inconclusive_not_failed_and_not_cached",
                  f"{T_READY}::test_readyz_503_when_a_probe_fails", f"{T_READY}::test_readyz_ok_with_real_database_file"],
        "ci": [ci("ci", PY312, "pytest with coverage"),
               ci("deploy-kind", None, "Smoke test through port-forward", [R("deploy/smoke.sh", r'status GET /readyz\)" == 200', "one")])],
    },
    {
        "id": "container", "layer": "container", "title": "Non-root user, read-only root filesystem, all capabilities dropped",
        "threat": tm("Container breakout from a root process", ("mitigation",)),
        "limits": [quote("docs/DEPLOYMENT.md", "There is a shell in the image", "(Debian slim ships `sh`).")],
        "code": [R("Dockerfile", r"^RUN apt-get update", r"^ && rm -rf /root/\.cache"), R("Dockerfile", r"^USER 10001:10001", "one"),
                 R("deploy/helm/kevgate/values.yaml", r"^podSecurityContext:"), R("deploy/helm/kevgate/values.yaml", r"^securityContext:")],
        "tests": [],
        "ci": [ci("security", "Image build, Trivy scan, SBOM", "Container runs read-only as UID 10001 and passes the smoke test"),
               ci("deploy-kind", None, "Prove restricted pod security context on the live pod")],
    },
    {
        "id": "netpol", "layer": "cluster", "title": "NetworkPolicy: ingress from labelled pods only, egress to DNS only",
        "threat": tm("Other pods scrape metrics or call the API"),
        "limits": [tm("Caller pretends to be a scanner or admin"), quote("docs/DEPLOYMENT.md", "No WAF, ingress controller or TLS termination.", "No WAF, ingress controller or TLS termination.")],
        "code": [R("deploy/helm/kevgate/templates/networkpolicy.yaml", r"^spec:"), R("deploy/helm/kevgate/values.yaml", r"^networkPolicy:")],
        "tests": [],
        "ci": [ci("deploy-kind", None, "NetworkPolicy, egress deny and Pod Security admission",
                  [R("deploy/scripts/netpol-test.sh", r"^client_pod np-allowed", r'^echo "ok   ingress'),
                   R("deploy/scripts/netpol-test.sh", r"^pod=\"\$\(kubectl", r'^echo "ok   egress')])],
    },
    {
        "id": "psa", "layer": "cluster", "title": "Pod Security Admission enforces the restricted profile on the namespace",
        "threat": tm("Container breakout from a root process", ("mitigation",)),
        "limits": [quote("docs/DEPLOYMENT.md", "No admission policy engine", "beyond Pod Security Admission.")],
        "code": [R("deploy/kind/namespace.yaml", r"^  labels:")],
        "tests": [],
        "ci": [ci("deploy-kind", None, "NetworkPolicy, egress deny and Pod Security admission",
                  [R("deploy/scripts/netpol-test.sh", r"^# Pod Security admission: privileged pod", r'^echo "ok   admission')])],
    },
    {
        "id": "alerts", "layer": "cluster", "title": "Prometheus alert rules for auth failures, forbidden use and rate limiting",
        "threat": quote("deploy/monitoring/kevgate-rules.yaml", "invalid suggests key guessing", "used outside its scopes."),
        "limits": [quote("docs/DEPLOYMENT.md", "Alert rules and the dashboard never ran against a live Prometheus.", "validation only.")],
        "code": [R("deploy/monitoring/kevgate-rules.yaml", r"^      - alert: KevgateAuthFailureSpike"),
                 R("deploy/monitoring/kevgate-rules.yaml", r"^      - alert: KevgateForbiddenScopeUse"),
                 R("deploy/monitoring/kevgate-rules.yaml", r"^      - alert: KevgateRateLimitSpike"),
                 R(SRC + "/metrics.py", r"# Create every labelled series now", r"self\.auth_failures\.labels\(reason\)\.inc\(0\)")],
        "tests": [f"{T_FAIL}::test_labelled_counters_exist_at_zero_on_startup", f"{T_FAIL}::test_first_forbidden_event_moves_series_from_zero",
                  f"{T_API}::test_auth_failures_counted"],
        "ci": [ci("security", "IaC and config scan (checkov, trivy, lint)", "promtool (rules, unit tests, CRD in sync)")],
    },
    {
        "id": "sigma", "layer": "cluster", "title": "Sigma rules for Kubernetes audit events",
        "threat": quote("deploy/detections/k8s_exec_into_kevgate_pod.yml", "Detects kubectl exec or attach into a kevgate pod.", "the SQLite database on /data."),
        "limits": [quote("docs/DEPLOYMENT.md", "The Sigma rules never ran in a SIEM.", "against a real kind audit log.")],
        "code": [R("deploy/detections/k8s_exec_into_kevgate_pod.yml", r"^detection:"),
                 R("deploy/detections/k8s_privileged_pod_in_kevgate_namespace.yml", r"^detection:"),
                 R("deploy/detections/k8s_kevgate_secret_read_by_other_sa.yml", r"^detection:"),
                 R("deploy/detections/k8s_ephemeral_container_in_kevgate_pod.yml", r"^detection:")],
        "tests": [],
        "ci": [ci("security", "IaC and config scan (checkov, trivy, lint)", "Sigma rules"),
               ci("deploy-kind", None, "Audit log contains the events the Sigma rules target",
                  [R("deploy/scripts/audit-check.sh", r'^check "k8s_exec_into_kevgate_pod"', r"\|\| rc=1$"),
                   R("deploy/scripts/audit-check.sh", r'^check "k8s_kevgate_secret_read_by_other_sa"', r"\|\| rc=1$"),
                   R("deploy/scripts/audit-check.sh", r'^check "k8s_privileged_pod_in_kevgate_namespace"', r"\|\| rc=1$")])],
        "note": "sigma_note",
    },
    {
        "id": "lock", "layer": "supply", "title": "Dependencies installed from a committed, hash-locked file",
        "threat": tm("Vulnerable dependency", ("mitigation",)),
        "limits": [quote("docs/PIPELINE.md", "Dependabot does not recognise", "is the check that covers it.")],
        "code": [R("Dockerfile", r"^COPY requirements\.lock \./", r"--require-hashes"), R(".github/dependabot.yml", r"^  - package-ecosystem: pip")],
        "tests": [],
        "ci": [ci("ci", PY312, "Install runtime dependencies from the hashed lock"),
               ci("security", "SCA (pip-audit on the hashed lock)", "pip-audit"),
               ci("security", "Image build, Trivy scan, SBOM", "Build image")],
    },
    {
        "id": "release", "layer": "supply", "title": "Release image signed, with SBOM and provenance attestations",
        "threat": quote("docs/PIPELINE.md", "The aim is that a pull request cannot reach", "proof of where it came from."),
        "limits": [quote("docs/DEPLOYMENT.md", "No image signature verification at admission.", "does not."),
                   quote("docs/DEPLOYMENT.md", "Verify the cosign signature at admission", "required checks for `main`.")],
        "code": [R(".github/workflows/release.yml", r"^      - name: Sign image \(keyless\) and attach SBOM attestation"),
                 R(".github/workflows/release.yml", r"^      - name: Build provenance attestation"),
                 R(".github/workflows/release.yml", r"^      - name: Verify what was just published")],
        "tests": [],
        "ci": [ci("release", None, "Sign image (keyless) and attach SBOM attestation"),
               ci("release", None, "Build provenance attestation"),
               ci("release", None, "Verify what was just published")],
        "registry": True,
    },
    {
        "id": "oidc", "layer": "cloud", "title": "CI role trust policy pinned to one repository and one branch",
        "threat": quote("docs/DEPLOYMENT.md", "The CI role's trust policy is the one place", "assume the role."),
        "limits": [quote("docs/THREAT_MODEL.md", "The CI role's trust policy is pinned by a `terraform test`", "The role has no consumer today."),
                   quote("docs/DEPLOYMENT.md", "It checks the policy as written in", "is not configured for this repository.")],
        "code": [R("infra/terraform/modules/kevgate/iam.tf", r'^data "aws_iam_policy_document" "github_ci_trust"', "brace"),
                 R("infra/terraform/modules/kevgate/variables.tf", r'^variable "github_branch"', "brace"),
                 R("infra/terraform/modules/kevgate/tests/oidc_trust.tftest.hcl", r'^run "trust_is_exact_main_branch_only"', "brace")],
        "tests": [],
        "ci": [ci("terraform", "OIDC trust policy regression (terraform test)", "Trust policy must be StringEquals on aud and one exact sub, no wildcard",
                  [R("infra/terraform/modules/kevgate/tests/oidc_trust.tftest.hcl", r'^run "wildcard_branch_is_rejected_by_validation"', "brace")])],
    },
]


# ---------------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------------
def sh(cmd: list[str], cwd: Path | None = None, ok: tuple[int, ...] = (0,)) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, check=False)
    out = p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if p.returncode not in ok:
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n{out}\n{p.stderr.decode('utf-8', 'replace')}")
    return out


def gh_api(path: str) -> dict:
    last = ""
    for attempt in range(4):
        p = subprocess.run(["gh", "api", path], capture_output=True, check=False)
        if p.returncode == 0:
            return json.loads(p.stdout.decode("utf-8"))
        last = p.stderr.decode("utf-8", "replace")
        time.sleep(3 * (attempt + 1))
    raise SystemExit(f"gh api {path} failed: {last}")


def http_json(url: str, headers: dict[str, str] | None = None) -> tuple[dict, dict]:
    last: Exception | None = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), dict(r.headers)
        except Exception as exc:  # noqa: BLE001 - retried, then reported
            last = exc
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"GET {url} failed: {last}")


def norm_map(raw: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed text and, for each of its characters, the offset in the original."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(raw):
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(out).rstrip(), idx


def find_quote(raw: str, start: str, end: str) -> tuple[str, int]:
    text, idx = norm_map(raw)
    s = text.find(start)
    if s < 0 or text.count(start) != 1:
        raise SystemExit(f"quote start {start!r} must occur exactly once")
    e = text.find(end, s)
    if e < 0:
        raise SystemExit(f"quote end {end!r} not found after {start!r}")
    e += len(end)
    line = raw.count("\n", 0, idx[s]) + 1
    return text[s:e], line


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def locate(repo: Path, spec: dict) -> dict:
    """Find the line range of a source reference by searching the file at the tag."""
    path, start, end = spec["path"], spec["start"], spec["end"]
    lines = (repo / path).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if re.search(start, ln)]
    if len(hits) != 1:
        raise SystemExit(f"{path}: start pattern {start!r} matches {len(hits)} lines, need exactly 1")
    i = hits[0]
    if end == "one":
        j = i
    elif end == "eof":
        j = max(k for k, ln in enumerate(lines) if ln.strip())
    elif end == "brace":
        ind = indent_of(lines[i])
        j = next(k for k in range(i + 1, len(lines)) if indent_of(lines[k]) == ind and lines[k].startswith(" " * ind + "}"))
    elif end is None:
        ind = indent_of(lines[i])
        j = i
        depth = lines[i].count("(") - lines[i].count(")")
        while depth > 0 and j + 1 < len(lines):  # a signature that spans several lines: the body starts after it
            j += 1
            depth += lines[j].count("(") - lines[j].count(")")
        for k in range(j + 1, len(lines)):
            if not lines[k].strip():
                continue
            if indent_of(lines[k]) <= ind:
                break
            j = k
    else:
        j = next((k for k in range(i, len(lines)) if re.search(end, lines[k])), -1)
        if j < 0:
            raise SystemExit(f"{path}: end pattern {end!r} not found after line {i + 1}")
    return {"path": path, "start": i + 1, "end": j + 1}


def threat_rows(text: str) -> list[dict]:
    rows, section = [], ""
    for n, ln in enumerate(text.split("\n"), 1):
        m = re.match(r"^## (\d+)\. (.+)$", ln)
        if m:
            section = m.group(1)
        if ln.startswith("| ") and not ln.startswith("|---") and not ln.startswith("| STRIDE"):
            cells = [c.strip() for c in ln.strip().strip("|").split(" | ")]
            if len(cells) != 4:
                raise SystemExit(f"THREAT_MODEL.md line {n}: expected 4 cells, got {len(cells)}")
            rows.append({"section": section, "line": n, "stride": cells[0], "threat": cells[1], "mitigation": cells[2], "residual": cells[3]})
    return rows


def versions(repo: Path, py: str) -> dict:
    code = "import importlib.metadata as m, sys; print(sys.version.split()[0]); print(m.version('pytest'))"
    py_v, pytest_v = sh([py, "-c", code]).split()
    return {"python": py_v, "pytest": pytest_v}


# ---------------------------------------------------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------------------------------------------------
def collect_tests(repo: Path, py: str) -> list[str]:
    out = sh([py, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider"], repo)
    ids = [ln.strip() for ln in out.split("\n") if "::" in ln]
    if not ids:
        raise SystemExit("pytest --collect-only found no tests")
    return ids


def run_cited(repo: Path, py: str, bases: list[str], want_cases: int) -> int:
    out = sh([py, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", "-q", "--no-header", *bases], repo, ok=(0, 1))
    m = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    if failed or not m or int(m.group(1)) != want_cases:
        raise SystemExit(f"cited tests did not all pass:\n{out[-1500:]}")
    return int(m.group(1))


def resolve_test(repo: Path, collected: list[str], base: str) -> dict:
    path, name = base.split("::")
    cases = [c for c in collected if c == base or c.startswith(base + "[")]
    if not cases:
        raise SystemExit(f"test {base} was not collected by pytest")
    ref = locate(repo, R(path, rf"^def {re.escape(name)}\(", None))
    return {"id": base, "path": path, "name": name, "cases": len(cases), "start": ref["start"], "end": ref["end"]}


def find_step(jobs: list[dict], job: str | None, step: str) -> tuple[dict, dict]:
    hits = [(j, s) for j in jobs if job is None or j["name"] == job for s in j["steps"] if s["name"] == step]
    if len(hits) != 1:
        raise SystemExit(f"CI step {step!r} (job {job!r}) matches {len(hits)} steps, need exactly 1")
    return hits[0]


def yaml_step(repo: Path, wf: str, step: str) -> dict:
    spec = R(f".github/workflows/{wf}.yml", rf"^      - name: {re.escape(step)}\s*$")
    return locate(repo, spec)


def registry() -> dict:
    tok, _ = http_json(f"https://ghcr.io/token?scope=repository:{OWNER_REPO}:pull&service=ghcr.io")
    auth = {"Authorization": "Bearer " + tok["token"]}
    base = f"https://ghcr.io/v2/{OWNER_REPO}/manifests/"
    _, hdr = http_json(base + IMAGE_TAG, {**auth, "Accept": "application/vnd.oci.image.manifest.v1+json"})
    digest = hdr.get("Docker-Content-Digest") or hdr.get("docker-content-digest")
    if not digest:
        raise SystemExit("registry returned no digest for the image tag")
    idx, _ = http_json(base + "sha256-" + digest.split(":")[1], {**auth, "Accept": "application/vnd.oci.image.index.v1+json"})
    kinds = sorted(m["annotations"]["dev.sigstore.bundle.predicateType"] for m in idx["manifests"])
    return {"image": IMAGE, "tag": IMAGE_TAG, "digest": digest, "anonymous_pull": True, "attached": kinds}


def capture(repo: Path, py: str) -> dict:
    head = sh(["git", "rev-parse", "HEAD"], repo).strip()
    if head != COMMIT:
        raise SystemExit(f"clone is at {head}, expected {COMMIT} ({TAG})")
    tm_text = (repo / "docs/THREAT_MODEL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    rows = threat_rows(tm_text)
    docs: dict[str, str] = {}

    def doc(path: str) -> str:
        if path not in docs:
            # Markdown bold markers are dropped so a quote can run across them; line numbers do not change.
            text = (repo / path).read_text(encoding="utf-8").replace("\r\n", "\n")
            docs[path] = text.replace("**", "")
        return docs[path]

    def tm_row(match: str) -> dict:
        hits = [r for r in rows if match in r["threat"]]
        if len(hits) != 1:
            raise SystemExit(f"THREAT_MODEL.md: {match!r} matches {len(hits)} rows, need exactly 1")
        return hits[0]

    def threat_of(spec: dict) -> dict:
        if spec["kind"] == "tm":
            r = tm_row(spec["match"])
            return {"text": r["threat"], "stride": r["stride"], "src": "docs/THREAT_MODEL.md", "line": r["line"], "sec": r["section"]}
        text, line = find_quote(doc(spec["doc"]), spec["start"], spec["end"])
        return {"text": text, "src": spec["doc"], "line": line}

    def limit_of(spec: dict) -> dict:
        if spec["kind"] == "tm":
            r = tm_row(spec["match"])
            return {"text": r["residual"], "src": "docs/THREAT_MODEL.md", "line": r["line"], "sec": r["section"]}
        text, line = find_quote(doc(spec["doc"]), spec["start"], spec["end"])
        return {"text": text, "src": spec["doc"], "line": line}

    collected = collect_tests(repo, py)
    runs_meta: dict[str, dict] = {}
    jobs_by_wf: dict[str, list[dict]] = {}
    for wf, rid in RUNS.items():
        r = gh_api(f"repos/{OWNER_REPO}/actions/runs/{rid}")
        jobs = gh_api(f"repos/{OWNER_REPO}/actions/runs/{rid}/jobs?per_page=100")["jobs"]
        if r["conclusion"] != "success":
            raise SystemExit(f"run {rid} ({wf}) is {r['conclusion']}, not success")
        runs_meta[wf] = {"id": rid, "workflow": r["name"], "sha": r["head_sha"][:7], "event": r["event"], "branch": r["head_branch"],
                         "date": r["created_at"][:10], "conclusion": r["conclusion"]}
        jobs_by_wf[wf] = jobs
    # the terraform run is for the previous commit: its inputs must equal the tag's
    sh(["git", "diff", "--quiet", TERRAFORM_RUN_SHA, TAG, "--", "infra", ".github/workflows/terraform.yml"], repo)
    for wf in ("ci", "security", "deploy-kind", "release"):
        if runs_meta[wf]["sha"] != COMMIT[:7]:
            raise SystemExit(f"run for {wf} is on {runs_meta[wf]['sha']}, not the tag commit")

    controls = []
    cited: dict[str, dict] = {}
    for spec in CONTROLS:
        c: dict = {"id": spec["id"], "layer": spec["layer"], "title": spec["title"], "threat": threat_of(spec["threat"]),
                   "limits": [limit_of(s) for s in spec["limits"]], "code": [locate(repo, s) for s in spec["code"]]}
        tests = []
        for base in spec["tests"]:
            t = cited.get(base) or resolve_test(repo, collected, base)
            cited[base] = t
            tests.append(t)
        c["tests"] = tests
        steps = []
        for e in spec["ci"]:
            j, s = find_step(jobs_by_wf[e["wf"]], e["job"], e["step"])
            loc = yaml_step(repo, e["wf"], e["step"])
            steps.append({"wf": e["wf"], "job": j["name"], "job_id": j["id"], "step": s["name"], "n": s["number"], "conclusion": s["conclusion"],
                          "src": loc, "asserts": [locate(repo, a) for a in e["asserts"]]})
            if s["conclusion"] != "success":
                raise SystemExit(f"step {s['name']!r} concluded {s['conclusion']}")
        c["ci"] = steps
        if spec.get("registry"):
            c["registry"] = registry()
        if spec.get("note") == "sigma_note":
            rules = len(list((repo / "deploy/detections").glob("*.yml")))
            checked = len(re.findall(r'^check "', (repo / "deploy/scripts/audit-check.sh").read_text(encoding="utf-8"), re.M))
            c["note"] = f"audit-check.sh checks {checked} of the {rules} rules against a real kind audit log; `sigma check` covers all {rules}."
        if not (c["tests"] or c["ci"]):
            raise SystemExit(f"control {spec['id']} has no test or CI step")
        controls.append(c)

    bases = sorted(cited)
    want = sum(cited[b]["cases"] for b in bases)
    passed = run_cited(repo, py, bases, want)
    v = versions(repo, py)
    return {
        "meta": {
            "tool": "kevgate", "tag": TAG, "commit": COMMIT[:7], "commit_full": COMMIT, "repo": REPO_URL, "captured": CAPTURED,
            "tests_total": len(collected), "tests_cited": len(bases), "test_cases_cited": want, "test_cases_passed": passed,
            "python": v["python"], "pytest": v["pytest"], "os": platform.platform(),
            "command": "pytest --collect-only, then pytest on each cited test; gh api actions/runs/ID/jobs; GHCR manifests",
        },
        "layers": LAYERS,
        "runs": runs_meta,
        "controls": controls,
    }


def comparable(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    for k in ("captured", "python", "pytest", "os"):
        d["meta"].pop(k, None)
    return d


def prepare(args: argparse.Namespace) -> tuple[Path, str, Path | None]:
    tmp: Path | None = None
    if args.clone:
        repo = Path(args.clone).resolve()
        sh(["git", "checkout", "-q", TAG], repo)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="kevgate-capture-"))
        repo = tmp / "kevgate"
        sh(["git", "clone", "-q", REPO_URL, str(repo)])
        sh(["git", "checkout", "-q", TAG], repo)
    if args.venv:
        venv = Path(args.venv).resolve()
    else:
        tmp = tmp or Path(tempfile.mkdtemp(prefix="kevgate-capture-"))
        venv = tmp / "venv"
        sh([sys.executable, "-m", "venv", str(venv)])
        sh([str(venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"), "-m", "pip", "install", "-q", "-e", ".[dev]"], repo)
    py = str(venv / ("Scripts" if sys.platform == "win32" else "bin") / "python")
    return repo, py, tmp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare a fresh capture with the stored file; write nothing")
    ap.add_argument("--clone", help="an existing clone of kevgate (checked out at the tag by this script)")
    ap.add_argument("--venv", help="a virtual environment with kevgate installed with its dev extras")
    args = ap.parse_args()
    repo, py, tmp = prepare(args)
    try:
        data = capture(repo, py)
        m = data["meta"]
        print(f"kevgate {m['tag']} commit {m['commit_full']}; Python {m['python']}, pytest {m['pytest']}, {platform.platform()}")
        print(f"{len(data['controls'])} controls, {m['tests_cited']} cited tests ({m['test_cases_cited']} cases, all passed) of {m['tests_total']} collected, "
              f"{sum(len(c['ci']) for c in data['controls'])} CI step citations")
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
        if args.check:
            stored = json.loads(OUT.read_text(encoding="utf-8"))
            same = comparable(stored) == comparable(data)
            print(f"checked kevgate-bench.json against a fresh capture of kevgate {m['tag']}: {'OK' if same else 'DIFFERENT'}")
            return 0 if same else 1
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT)} ({len(text)} bytes)")
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
