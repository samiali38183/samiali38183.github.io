#!/usr/bin/env python3
"""Re-run the six mutants of the kevgate page against kevgate v0.1.0 (its 227 tests) and v0.1.1 (its 277 tests).

  python scripts/rerun_kevgate_mutants.py --clone DIR --python VENV_PYTHON

DIR is a clone of https://github.com/samiali38183/kevgate with both tags and VENV_PYTHON an interpreter that has the project's dev
extras installed (pytest, httpx, hypothesis). The script adds a temporary git worktree per tag, applies one mutation at a time to the
source in the worktree (the clone is not modified), runs the suite with PYTHONPATH pointing at that worktree and prints whether any
test failed. Expected: every mutant survives at v0.1.0 and is killed at v0.1.1. Exit status 1 otherwise.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# (name, file, old text that must occur exactly once, new text)
MUTANTS = [
    ("early-exit key comparison", "src/kevgate/auth.py", "                match = key\n", "                match = key\n                break\n"),
    ("== in place of compare_digest", "src/kevgate/auth.py", "hmac.compare_digest(digest, key.digest)", "(digest == key.digest)"),
    ("BEGIN instead of BEGIN IMMEDIATE", "src/kevgate/db.py", 'self._conn.execute("BEGIN IMMEDIATE")\n            try:\n                yield', 'self._conn.execute("BEGIN")\n            try:\n                yield'),
    ("body size counted from the last chunk only", "src/kevgate/middleware.py", 'received += len(message.get("body", b""))', 'received = len(message.get("body", b""))'),
    ("CSV merge taking the minimum CVSS", "src/kevgate/csv_import.py", '"cvss": max(a.cvss, b.cvss)', '"cvss": min(a.cvss, b.cvss)'),
    ("upsert skipping EPSS", "src/kevgate/db.py", "    epss = excluded.epss,\n", ""),
]
EXPECTED_TESTS = {"v0.1.0": 227, "v0.1.1": 277}


def pytest(py: str, wt: Path, *extra: str) -> tuple[int, str]:
    env = dict(os.environ, PYTHONPATH=str(wt / "src"))
    p = subprocess.run([py, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", "-q", "--no-header", *extra], cwd=wt, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = [ln for ln in p.stdout.splitlines() if ln.strip()][-1]
    return p.returncode, last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone", required=True)
    ap.add_argument("--python", required=True)
    a = ap.parse_args()
    clone = Path(a.clone).resolve()
    ok = True
    with tempfile.TemporaryDirectory(prefix="kevgate-mutants-") as tmp:
        for tag, want_killed in (("v0.1.0", False), ("v0.1.1", True)):
            wt = Path(tmp) / tag
            subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), tag], cwd=clone, check=True)
            try:
                _, col = pytest(a.python, wt, "--collect-only")
                n = int(col.split()[0])
                rc, last = pytest(a.python, wt)
                print(f"{tag}: {n} tests collected; unmodified source: {last}")
                ok = ok and n == EXPECTED_TESTS[tag] and rc == 0
                for name, path, old, new in MUTANTS:
                    fp = wt / path
                    src = fp.read_text(encoding="utf-8")
                    if src.count(old) != 1:
                        raise SystemExit(f"{tag} {path}: mutation text occurs {src.count(old)} times")
                    fp.write_text(src.replace(old, new), encoding="utf-8", newline="")
                    try:
                        rc, last = pytest(a.python, wt, "-x")
                    finally:
                        fp.write_text(src, encoding="utf-8", newline="")
                    killed = rc != 0
                    ok = ok and killed == want_killed
                    print(f"  {'killed  ' if killed else 'survived'}  {name}: {last}")
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=clone, check=False, capture_output=True)
    print("OK" if ok else "UNEXPECTED RESULT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
