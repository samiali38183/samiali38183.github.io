#!/usr/bin/env python3
"""Render the Open Graph cards in assets/og/ (1200x630 PNG) with headless Chrome.

Usage: python scripts/og/make_og.py [path to chrome]
Each card is text only, set in the site's fonts: the project name, its headline figure and one line, all taken from
content/data/projects.json. No generated art. Needs Chrome or Chromium; the PNGs are committed, so the site build does not.
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

CARD = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:S;src:url("{fonts}/source-serif-4-latin-wght-normal.woff2");font-weight:200 900}}
@font-face{{font-family:M;src:url("{fonts}/ibm-plex-mono-latin-400-normal.woff2");font-weight:400}}
@font-face{{font-family:M;src:url("{fonts}/ibm-plex-mono-latin-600-normal.woff2");font-weight:600}}
*{{box-sizing:border-box;margin:0}}
body{{width:1200px;height:630px;background:#FAF8F3;color:#1B1D21;font-family:S;padding:56px 72px;position:relative;overflow:hidden}}
.top{{font:400 24px/1 M;color:#4A4D54;display:flex;justify-content:space-between}}
.name{{font:600 {name_size}px/1 S;letter-spacing:-.03em;margin-top:{name_top}px}}
.kind{{font:400 24px/1.3 M;color:#4A4D54;margin-top:18px}}
.big{{font:600 {big_size}px/1 M;letter-spacing:-.04em;margin-top:{big_top}px}}
.line{{font:400 32px/1.3 S;color:#1B1D21;margin-top:20px;max-width:1000px}}
.foot{{position:absolute;left:72px;bottom:30px;font:400 22px/1 M;color:#4A4D54}}
</style></head><body>
<div class="top"><span>Sami Ali</span><span>samiali38183.github.io</span></div>
{body}
</body></html>
"""


def render(chrome: str, html_text: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "card.html"
        page.write_text(html_text, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=1200,630", "--allow-file-access-from-files", "--virtual-time-budget=3000",
                        f"--screenshot={out}", page.as_uri()], check=True, capture_output=True)


def main() -> None:
    chrome = sys.argv[1] if len(sys.argv) > 1 else next((c for c in CHROME if Path(c).exists()), "chrome")
    fonts = (ROOT / "assets/fonts").as_uri()
    out_dir = ROOT / "assets/og"
    out_dir.mkdir(exist_ok=True)
    d = json.loads((ROOT / "content/data/projects.json").read_text(encoding="utf-8"))
    for slug in d["order"]:
        p = d["projects"][slug]
        body = (f'<div class="name">{html.escape(p["name"])}</div><div class="kind">{html.escape(p["kind"])} &middot; {html.escape(p["version"])}</div>'
                f'<div class="big">{html.escape(p["og"]["big"])}</div><div class="line">{html.escape(p["og"]["line"])}</div>'
                f'<div class="foot">{html.escape(p["label"])}</div>')
        render(chrome, CARD.format(fonts=fonts, name_size=76, name_top=64, big_size=120, big_top=24, body=body), out_dir / f"{slug}.png")
        print("wrote", slug)
    body = ('<div class="name">call-kettle</div><div class="kind">AI agent security &middot; Python</div>'
            '<div class="big">48 of 48</div><div class="line">evaluation cases pass: 42 attacks and 6 normal-use controls. Scripted model, synthetic data.</div>'
            '<div class="foot">Recorded run, scripted model</div>')
    render(chrome, CARD.format(fonts=fonts, name_size=76, name_top=64, big_size=120, big_top=24, body=body), out_dir / "call-kettle.png")
    print("wrote call-kettle")
    body = ('<div class="name" style="max-width:1000px">Security engineering student</div>'
            '<div class="line" style="margin-top:28px;font-size:40px">Building application-security and detection tools, with measured results.</div>'
            '<div class="kind" style="margin-top:24px">George Mason University, expected May 2028</div>'
            '<div class="foot">tripline &middot; sinkline &middot; kevgate &middot; call-kettle</div>')
    render(chrome, CARD.format(fonts=fonts, name_size=96, name_top=72, big_size=10, big_top=0, body=body), out_dir / "home.png")
    print("wrote home")


if __name__ == "__main__":
    main()
