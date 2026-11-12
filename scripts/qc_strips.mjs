// QC check: ruler strips must not wrap. Usage:
//   PUPPETEER_DIR=path/to/node_modules CHROME="path/to/chrome" node scripts/qc_strips.mjs http://127.0.0.1:8000
// Loads every page at 360, 768, 1280 and 1600 px in headless Chrome, opens every details element, and checks that all ticks of each
// `.strip` share one offsetTop (one row). Strips with class `long` (more than 40 ticks: the 255-tick evasion sweep, the 109-tick
// gate strip and similar) are multi-row rulers by design and are reported, not failed. Also fails on horizontal page overflow and on
// a mini strip narrower than its ticks need. Exit code 1 on any failure.
import { createRequire } from 'node:module';
import { join } from 'node:path';

const base = process.argv[2] || 'http://127.0.0.1:8000';
const require = createRequire(join(process.env.PUPPETEER_DIR || '.', 'x.js'));
const puppeteer = require('puppeteer-core');
const executablePath = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const pages = ['/', '/projects/', ...['tripline', 'sinkline', 'vulnlab', 'kevgate', 'kevgate-admit', 'fuzzdiff', 'kev-risk-prioritization'].map((s) => `/projects/${s}/`),
  '/about/', '/experience/', '/resume/'];
const widths = [360, 768, 1280, 1600];

const browser = await puppeteer.launch({ executablePath, headless: 'new' });
let strips = 0, long = 0, bad = 0;
for (const scheme of ['light', 'dark']) {
  for (const w of widths) {
    const pg = await browser.newPage();
    await pg.setViewport({ width: w, height: 900 });
    await pg.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }, { name: 'prefers-reduced-motion', value: 'reduce' }]);
    for (const p of pages) {
      await pg.goto(base + p, { waitUntil: 'networkidle0' });
      await pg.evaluate(() => { document.querySelectorAll('details').forEach((d) => { d.open = true; }); return document.fonts.ready; });
      const r = await pg.evaluate(() => {
        const out = { strips: 0, long: 0, wrapped: [], overflow: document.documentElement.scrollWidth > window.innerWidth };
        for (const s of document.querySelectorAll('.strip')) {
          const ticks = [...s.querySelectorAll(':scope > i')];
          if (ticks.length < 2 || s.getBoundingClientRect().width === 0) continue;
          if (s.classList.contains('long')) { out.long++; continue; }
          out.strips++;
          const tops = new Set(ticks.map((t) => Math.round(t.getBoundingClientRect().top)));
          const right = Math.max(...ticks.map((t) => t.getBoundingClientRect().right));
          const box = s.getBoundingClientRect();
          if (tops.size > 1 || right > box.right + 1) out.wrapped.push({ ticks: ticks.length, rows: tops.size, label: (s.getAttribute('aria-label') || s.className || '').slice(0, 60) });
        }
        return out;
      });
      strips += r.strips; long += r.long;
      if (r.wrapped.length || r.overflow) {
        bad++;
        console.log(`FAIL ${scheme} ${w}px ${p}: ${r.overflow ? 'horizontal overflow; ' : ''}${JSON.stringify(r.wrapped)}`);
      }
    }
    await pg.close();
  }
}
await browser.close();
console.log(`checked ${strips} single-row strips (and skipped ${long} long multi-row rulers) on ${pages.length} pages x ${widths.length} widths x 2 schemes; failures: ${bad}`);
process.exit(bad ? 1 : 0);
