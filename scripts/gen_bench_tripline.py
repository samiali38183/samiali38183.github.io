#!/usr/bin/env python3
"""Generate the data behind the tripline "Rule bench" from tripline itself.

Usage: python scripts/gen_bench_tripline.py --tripline PATH_TO_CLONE

Run it with a Python that has tripline installed from that clone (pip install PATH_TO_CLONE).
Writes:
  assets/data/bench-tripline.json         what the page loads: rule patterns (read from the rule YAML),
                                          the 36 recorded events with recorded verdicts, the presets
  assets/data/tripline-bench-parity.json  ground truth for scripts/test_bench_tripline.mjs: every preset,
                                          the 36 events and random chmod-like strings, evaluated by
                                          tripline's own Sigma compiler (tripline.engine)

The ground-truth verdicts come from `tripline.engine.rules.evaluate`, not from the patterns in this file.
The per-condition booleans (selection_* of each rule) come from Python `re` run on the patterns read from
the YAML; the generator asserts that they combine to the compiler's verdict for every case.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml
from tripline.engine.rules import evaluate, load_rules
from tripline.events import read_ndjson
from tripline.logsource import normalize

SITE = Path(__file__).resolve().parent.parent
STOCK_ID = "c21c4eaa-ba2e-419a-92b2-8371703cbe21"
CUSTOM_ID = "7f3c2b1a-6d4e-4a9b-9c8d-1e2f3a4b5c6d"
STOCK_FILE = "rules/sigma/linux/proc_creation_lnx_setgid_setuid.yml"
CUSTOM_FILE = "rules/sigma/linux/tripline_lnx_chmod_setuid_setgid_any_form.yml"
FIXTURE = "fixtures/linux/t1548-001-setuid-setgid/run.ndjson"
RUN = "41838714456"
TRIM = 110

# label, image, command line (what the visitor sees first)
PRESETS = [
    ("Recorded: sh -c wrapper", "/usr/bin/dash",
     "sh -c sudo touch /tmp/evilBinary; sudo chown root /tmp/evilBinary; sudo chmod u+xs /tmp/evilBinary"),
    ("Recorded: u+xs", "/usr/bin/chmod", "chmod u+xs /tmp/evilBinary"),
    ("Recorded: g+xs", "/usr/bin/chmod", "chmod g+xs /tmp/evilBinary"),
    ("chown root, then chmod u+s", "/usr/bin/dash", "sh -c chown root /tmp/x && chmod u+s /tmp/x"),
    ("Octal 4755", "/usr/bin/chmod", "chmod 4755 /tmp/x"),
    ("ug+s", "/usr/bin/chmod", "chmod ug+s /tmp/x"),
    ("a+s", "/usr/bin/chmod", "chmod a+s /tmp/x"),
    ("Octal 3755", "/usr/bin/chmod", "chmod 3755 /tmp/x"),
    ("Octal 04755", "/usr/bin/chmod", "chmod 04755 /tmp/x"),
    ("Clause list g+w,u+s", "/usr/bin/chmod", "chmod g+w,u+s /tmp/x"),
    ("Full path, u+xs", "/usr/bin/chmod", "/usr/bin/chmod u+xs /tmp/x"),
    ("Doc path appended", "/usr/bin/chmod", "chmod 4755 /tmp/x /usr/share/doc/x"),
    ("Only under /usr/share/doc/", "/usr/bin/chmod", "chmod u+s /usr/share/doc/pkg/helper"),
    ("Benign 644", "/usr/bin/chmod", "chmod 644 /tmp/x"),
    # Variants from the evasion sweep (docs/robustness.md at tripline v0.3.0, seed 20261111); each is checked against the compiler below
    ("Sweep: busybox multicall", "/usr/bin/busybox", "busybox chmod u+s f"),
    ("Sweep: clustered flags -vR", "/usr/bin/chmod", "chmod -vR 4755 /tmp/evilBinary"),
    ("Sweep: flag after mode", "/usr/bin/chmod", "chmod u+s -v /tmp/evilBinary"),
    ("Sweep: install -m 4755 (missed)", "/usr/bin/install", "install -m 4755 /tmp/src /tmp/dst"),
    ("Sweep: renamed copy (missed)", "/tmp/.c", "/tmp/.c u+s f"),
]


def conditions(stock: dict, custom: dict, image: str, cmd: str) -> tuple[list[int], list[int]]:
    """selection_* booleans via Python re on the YAML patterns (flags as tripline applies them)."""
    contains = lambda needle: re.search(re.escape(needle), cmd, re.I | re.S) is not None  # noqa: E731
    root = contains(stock["root"][0])
    perm = any(contains(n) for n in stock["perm"])
    img = any(re.fullmatch(".*" + re.escape(x), image, re.I | re.S) for x in custom["image"])
    sym = re.search(custom["symbolic"], cmd) is not None
    octal = re.search(custom["octal"], cmd) is not None
    filt = re.search(custom["filter"], cmd) is not None
    return ([int(root), int(perm), int(root and perm)],
            [int(img), int(sym), int(octal), int(filt), int(img and (sym or octal) and not filt)])


def reasons(sc: list[int], cc: list[int]) -> list[str]:
    """Short reason strings; the bench JavaScript must produce the same text (checked by the Node test)."""
    root, perm, sv = sc
    im, sy, oc, fi, rv = cc
    if sv:
        stock = "Has both 'chown root' and the literal ' chmod u+s' or ' chmod g+s'."
    elif not root and not perm:
        stock = "Has neither 'chown root' nor the literal ' chmod u+s' or ' chmod g+s'."
    elif not root:
        stock = "Has the chmod text but no 'chown root'; the rule needs both."
    else:
        stock = "Has 'chown root' but not the literal ' chmod u+s' or ' chmod g+s'; the rule needs both."
    if rv:
        form = "symbolic and octal" if sy and oc else "symbolic" if sy else "octal"
        custom = f"Image ends with /chmod or /busybox and the mode sets setuid or setgid ({form} form)."
    elif not im:
        custom = ("The mode would match, but Image does not end with /chmod or /busybox, so this event is not a chmod execution."
                  if sy or oc else "Image does not end with /chmod or /busybox and no setuid or setgid mode is present.")
    elif not (sy or oc):
        custom = "No setuid or setgid mode: no symbolic s bit and no octal mode 2xxx to 7xxx."
    else:
        custom = "Excluded: every file operand is under /usr/share/doc/."
    return [stock, custom]


def random_cases(rng: random.Random, n: int) -> list[tuple[str, str]]:
    images = ["/usr/bin/chmod", "/usr/bin/chmod", "/bin/chmod", "/usr/bin/sudo", "/usr/bin/dash", "/usr/bin/CHMOD",
              "/opt/chmod", "/chmod", "chmod", "/usr/bin/chmod ", "/usr/bin/chmodx", "/usr/bin/chmod\n", "",
              "/usr/bin/busybox", "/bin/BusyBox", "/busybox", "/usr/bin/busyboxx"]
    prefixes = ["", "", "", "sudo ", "/usr/bin/", "sh -c ", "sudo /bin/", "chown root x; ", "x chmod ", "xchmod ", "./", "  ",
                "env X=1 ", "\tsudo "]
    opts = ["", "", "-R ", "-f ", "--recursive ", "-Rf ", "-- ", "--reference=x ", "-1 ", "-v -c "]
    operands = ["/tmp/x", "/tmp/x", "/usr/share/doc/foo", "/usr/share/doc/a /usr/share/doc/b", "/tmp/x /usr/share/doc/foo",
                "/usr/share/doc/foo /tmp/x", "/usr/share/doc/../../tmp/x", "/usr/share/doc/", "/usr/share/doc", "",
                "/usr/share/doc/pkg/changelog.gz", "/usr/share/doc/x\t", "/usr/share/doc/ünï", "/usr/share/doc/x.",
                "/usr/share/doc/x..", "/usr/share/doc/a b", "/usr/share/docs/x", "/tmp/usr/share/doc/x", "a /usr/share/doc/x b",
                "/usr/share/doc/x　/usr/share/doc/y", "/usr/share/doc/x /tmp/y", "/usr/share/doc/٣"]
    suffixes = ["", "", "", " ", "\t", "\n", " \n", " # c", ";", " && echo", " ", " ", "\x85", "\x1c", "﻿", "\r\n"]
    seps = [" ", " ", " ", "  ", "\t", " ", " ", "\x1c", "\x85", "﻿", "　"]

    def sym_clause() -> str:
        who = "".join(rng.choice("ugoa") for _ in range(rng.choice([0, 1, 1, 2, 3])))
        perms = "".join(rng.choice("rwxXst") for _ in range(rng.choice([0, 1, 1, 2, 3, 4])))
        if rng.random() < 0.25:
            perms = rng.choice(["s", "xs", "sx", "rs", "ts", "Xs", "us"]) if rng.random() < .8 else perms
        return who + rng.choice("+-=++=") + perms

    def mode() -> str:
        r = rng.random()
        if r < 0.45:
            clauses = [sym_clause() for _ in range(rng.choice([1, 1, 2, 3]))]
            glue = rng.choice([",", ",", ",", ", ", " ,", ",,"])
            m = glue.join(clauses)
            return m + rng.choice(["", "", "", ","])
        if r < 0.85:
            ln = rng.choice([3, 4, 4, 4, 5, 2])
            digits = "".join(rng.choice("01234567" if rng.random() < .93 else "01234567890123456789") for _ in range(ln))
            return digits
        return rng.choice(["", "u+s", "g+s", "4755", "+s", "u-s", "1755", "0755", "-R", "4755x", "u+s,", "０４７５５", "a+s;"])

    out: list[tuple[str, str]] = []
    for _ in range(n):
        if rng.random() < 0.3:  # shapes aimed at the stock rule
            core = rng.choice(["chown root /tmp/x && chmod u+s /tmp/x", "sudo chown root x; sudo chmod g+s x",
                               "chown root f ; chmod u+s f", "CHOWN ROOT f; CHMOD U+S f", "chown  root f; chmod u+s f",
                               "chown root f; chmod u+xs f", "chown root f; chmod g+s f", "chown roo f; chmod u+s f",
                               "x chmod u+s y chown root", "chown root:root f &&chmod g+s f", "chown root f chmod u+s f"])
            cmd = rng.choice(["", "sh -c "]) + core
        else:
            sep = rng.choice(seps)
            cmd = (rng.choice(prefixes) + "chmod" + sep + rng.choice(opts) + mode() + sep + rng.choice(operands)
                   + rng.choice(suffixes))
            if rng.random() < 0.08:
                cmd = cmd.upper() if rng.random() < .5 else cmd.replace("chmod", "Chmod")
            if rng.random() < 0.04:
                cmd = cmd.replace("s", "ſ", 1)
        out.append((rng.choice(images), cmd))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tripline", required=True, type=Path)
    ap.add_argument("--random", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261111)
    args = ap.parse_args()
    repo: Path = args.tripline

    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    version = re.search(r'^version = "([^"]+)"', (repo / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    rules = load_rules(repo / "rules")
    assert not rules.errors, rules.errors
    c_stock, c_custom = rules.by_id(STOCK_ID), rules.by_id(CUSTOM_ID)
    assert c_stock and c_custom

    ys = yaml.safe_load((repo / STOCK_FILE).read_text(encoding="utf-8"))["detection"]
    yc = yaml.safe_load((repo / CUSTOM_FILE).read_text(encoding="utf-8"))["detection"]
    stock = {"root": [ys["selection_root"]["CommandLine|contains"]], "perm": ys["selection_perm"]["CommandLine|contains"]}
    image_sel = yc["selection_image"]["Image|endswith"]
    custom = {"image": [image_sel] if isinstance(image_sel, str) else list(image_sel), "symbolic": yc["selection_symbolic"]["CommandLine|re"],
              "octal": yc["selection_octal"]["CommandLine|re"], "filter": yc["filter_tmp_runner"]["CommandLine|re"]}
    assert ys["condition"] == "all of selection_*", ys["condition"]
    assert yc["condition"] == "selection_image and (selection_symbolic or selection_octal) and not filter_tmp_runner"

    def truth(image: str, cmd: str) -> dict:
        ev = {"type": "EXECVE", "Image": image, "CommandLine": cmd}
        a, b = evaluate(c_stock, ev), evaluate(c_custom, ev)
        assert a is not None and b is not None, "synthetic event not routed to linux process_creation"
        sc, cc = conditions(stock, custom, image, cmd)
        assert (bool(sc[2]), bool(cc[4])) == (a, b), (image, cmd, sc, cc, a, b)
        return {"i": image, "c": cmd, "s": sc, "r": cc, "w": reasons(sc, cc)}

    cases: list[dict] = []
    for label, image, cmd in PRESETS:
        cases.append({**truth(image, cmd), "g": "preset"})

    events = []
    fixture = read_ndjson(repo / FIXTURE)
    for raw in fixture:
        a, b = evaluate(c_stock, raw), evaluate(c_custom, raw)
        if a is None:
            assert b is None
            continue
        ne = normalize(raw)
        t = truth(ne["Image"], ne["CommandLine"])
        assert (bool(t["s"][2]), bool(t["r"][4])) == (a, b)
        cases.append({**t, "g": "fixture"})
        cmd = ne["CommandLine"]
        events.append({"i": ne["Image"], "c": cmd if len(cmd) <= TRIM else cmd[:TRIM] + "…", "s": int(a), "r": int(b)})
    assert len(events) == 36 and sum(e["s"] for e in events) == 0 and sum(e["r"] for e in events) == 2, "published numbers changed"

    rng = random.Random(args.seed)
    for image, cmd in random_cases(rng, args.random):
        cases.append({**truth(image, cmd), "g": "random"})

    expected_idx = [k for k, e in enumerate(events) if e["r"]]
    for e in events:  # secrets: nothing but image and a trimmed command line is kept; scan anyway
        assert not re.search(r"(?i)(token|secret|passw|api[_-]?key|AKIA[0-9A-Z]{12})", e["i"] + e["c"]), e

    presets = []
    for label, image, cmd in PRESETS:
        t = truth(image, cmd)
        presets.append({"l": label, "i": image, "c": cmd})
        assert t
    data = {
        "meta": {
            "tripline": version, "commit": commit, "date": str(date.today()), "run": RUN, "fixture": FIXTURE,
            "stock": {"id": STOCK_ID, "file": STOCK_FILE}, "custom": {"id": CUSTOM_ID, "file": CUSTOM_FILE},
            "parity_cases": len(cases), "trim": TRIM,
        },
        "stock": stock, "custom": custom, "presets": presets, "events": events, "expected": expected_idx,
    }
    (SITE / "assets/data").mkdir(parents=True, exist_ok=True)
    (SITE / "assets/data/bench-tripline.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    parity = {"meta": {**data["meta"], "how": "tripline.engine.rules.evaluate on synthetic EXECVE events {Image, CommandLine}",
                       "seed": args.seed, "fields": "s=[root,perm,verdict] r=[image,symbolic,octal,filter,verdict] w=[stock reason, replacement reason]"},
              "cases": cases}
    (SITE / "assets/data/tripline-bench-parity.json").write_text(
        json.dumps(parity, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    n_s = sum(c["s"][2] for c in cases)
    n_r = sum(c["r"][4] for c in cases)
    print(f"cases {len(cases)} (presets {len(PRESETS)}, fixture 36, random {args.random}); stock true {n_s}, replacement true {n_r}; "
          f"expected event indexes {expected_idx}; tripline {version} {commit}")


if __name__ == "__main__":
    sys.exit(main())
