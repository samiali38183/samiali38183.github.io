#!/usr/bin/env python3
"""Check internal links, anchors, images and external links.

Usage: python scripts/check_links.py [BASE_URL]
With no argument it checks the files in the working tree; with a base URL it crawls the live site.
Requires: requests.
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (link check)"}
BOT_BLOCKED_HOSTS = {"www.linkedin.com", "linkedin.com"}


class Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.links.append(a[k])
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url=(\S+)", a.get("content", ""))
            if m:
                self.links.append(m.group(1))


def local_pages() -> dict[str, str]:
    pages = {}
    for f in ROOT.rglob("*.html"):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(("content/", "node_modules/")) or rel.startswith("_"):
            continue
        url = "/" + rel
        if rel.endswith("index.html"):
            url = "/" + rel[: -len("index.html")]
        pages[url] = f.read_text(encoding="utf-8")
    return pages


def resolve_local(path: str) -> Path | None:
    p = ROOT / path.lstrip("/")
    if p.is_file():
        return p
    if p.is_dir() and (p / "index.html").is_file():
        return p / "index.html"
    return None


def main() -> int:
    live = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None
    problems: list[str] = []
    ext: dict[str, list[str]] = {}
    internal_count = 0
    if live:
        pages = {}
        for u in ["/", "/projects/", "/projects/tripline/", "/projects/sinkline/", "/projects/kevgate/", "/projects/kevgate-admit/", "/projects/fuzzdiff/",
                  "/projects/kev-risk-prioritization/", "/experience/", "/about/", "/resume/", "/404.html"]:
            r = requests.get(live + u, headers=UA, timeout=30)
            pages[u] = r.text
    else:
        pages = local_pages()
    parsed = {}
    for url, text in pages.items():
        c = Collect()
        c.feed(text)
        parsed[url] = c
    for url, c in parsed.items():
        for link in c.links:
            if link.startswith(("mailto:", "tel:", "data:")):
                continue
            full = urljoin("https://x.test" + url, link)
            pu = urlparse(full)
            if pu.netloc == "samiali38183.github.io" and not live and not pu.path.startswith(("/tripline/", "/sinkline/")):
                # canonical and og:url point at the live domain; check them against the working tree
                pu = pu._replace(netloc="x.test")
            if pu.netloc not in ("x.test", urlparse(live).netloc if live else ""):
                ext.setdefault(urldefrag(full)[0], []).append(url)
                continue
            internal_count += 1
            path, frag = pu.path, pu.fragment
            if live:
                r = requests.get(live + path, headers=UA, timeout=30)
                if r.status_code != 200:
                    problems.append(f"{url}: {link} -> HTTP {r.status_code}")
                    continue
            else:
                if resolve_local(path) is None:
                    problems.append(f"{url}: {link} -> missing file")
                    continue
            if frag:
                target = parsed.get(path if path in parsed else path.rstrip("/") + "/")
                if target is None or frag not in target.ids:
                    problems.append(f"{url}: {link} -> anchor #{frag} not found")

    def head(u: str) -> tuple[str, str]:
        host = urlparse(u).netloc
        try:
            r = requests.get(u, headers=UA, timeout=30, allow_redirects=True, stream=True)
            code = r.status_code
            r.close()
        except requests.RequestException as e:
            return u, f"ERR {type(e).__name__}"
        if code >= 400 and host in BOT_BLOCKED_HOSTS:
            return u, f"bot-blocked ({code})"
        return u, str(code)

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(head, sorted(ext)))
    for u, code in results:
        ok = code.startswith(("2", "3", "bot-blocked"))
        print(("ok   " if ok else "FAIL ") + code.ljust(18) + u)
        if not ok:
            problems.append(f"external {u} -> {code}")
    print(f"\ninternal links checked: {internal_count}; external unique: {len(ext)}")
    for p in problems:
        print("PROBLEM:", p)
    print("RESULT:", "FAIL" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
