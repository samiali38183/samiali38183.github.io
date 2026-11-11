// Parity test for the kev-risk-prioritization Weight bench. Usage: node scripts/test_bench_kev.mjs
// Loads the bench's scoring (assets/js/bench-kev-risk.js, findings from assets/data/bench-kev-risk.json) and asserts
// that rank order and every score (one decimal, as the tool prints) equal what kev_prioritize.score_all returned for
// the four presets and the random weight vectors in assets/data/kev-bench-parity.json (written by
// scripts/gen_bench_kev.py). The default preset is also compared with the tool's printed table, line by line.
// Exit code 1 on any difference.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { rank, round1 as roundForTest, view, kevInTop } from '../assets/js/bench-kev-risk.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const read = (p) => JSON.parse(readFileSync(root + p, 'utf8'));
const data = read('assets/data/bench-kev-risk.json');
const parity = read('assets/data/kev-bench-parity.json');
const F = data.findings;
const bad = [];
const by = {};

for (const c of parity.cases) {
  const got = rank(F, c.w);
  const ok = JSON.stringify(got.o) === JSON.stringify(c.o) && JSON.stringify(got.s) === JSON.stringify(c.s);
  by[c.g] = by[c.g] || { n: 0, bad: 0 };
  by[c.g].n++;
  if (!ok) { by[c.g].bad++; bad.push({ group: c.g, w: c.w, want: { o: c.o, s: c.s }, got }); }
}

// Default weights against the tool's printed output (rank, score, KEV flag, CVE, CVSS, EPSS, ACR, days, asset).
const rows = view(data, data.presets[0].w);
rows.forEach((r, i) => {
  const line = `${String(r.rank).padStart(3)} ${r.score.toFixed(1).padStart(5)}  ${(r.kev ? 'yes' : '-').padEnd(3)} ${r.cve.padEnd(16)} `
    + `${r.cvss.toFixed(1).padStart(4)} ${r.epss.toFixed(3).padStart(5)} ${String(r.acr).padStart(3)} ${String(r.days).padStart(4)}  ${r.asset}`;
  if (line !== parity.cli_default[i]) bad.push({ group: 'cli', want: parity.cli_default[i], got: line });
});

// Headline counts on the page: KEV findings among the top 12 for each preset.
const want = parity.meta.kev_in_top;
for (const p of data.presets) {
  const n = kevInTop(F, rank(F, p.w).o, data.top);
  if (n !== want[p.k]) bad.push({ group: 'counts', preset: p.k, n, want: want[p.k] });
  console.log(`${p.k.padEnd(8)} KEV in top ${data.top}: ${n}`);
}
if (want.default !== 12 || want.cvss !== 9) bad.push({ group: 'page claim', want });

// Rounding: exact ties at one decimal go to the even tenth (Python's round); everything else rounds the exact value.
for (const [x, want1] of [[95.25, 95.2], [95.75, 95.8], [0.15, 0.1], [2.675, 2.7], [99.95, 100]]) {
  const got = roundForTest(x);
  if (got !== want1) bad.push({ group: 'round', x, want1, got });
}

for (const [g, v] of Object.entries(by)) console.log(`${g.padEnd(8)} ${String(v.n).padStart(4)} cases, ${v.bad} differences`);
if (bad.length) {
  console.log(JSON.stringify(bad.slice(0, 5), null, 1));
  console.log(`FAIL: ${bad.length} differences`);
  process.exit(1);
}
console.log(`OK: ${parity.cases.length} cases and the 20 printed lines match kev-risk-prioritization ${parity.meta.tag} (${parity.meta.commit})`);
