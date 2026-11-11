// Parity test for the tripline Rule bench. Usage: node scripts/test_bench_tripline.mjs
// Loads the bench's rule logic (assets/js/bench-tripline.js, rule patterns from assets/data/bench-tripline.json)
// and asserts that it gives the same selection results, verdicts and reasons as tripline's own Sigma compiler,
// whose output is stored in assets/data/tripline-bench-parity.json by scripts/gen_bench_tripline.py.
// Exit code 1 on any difference.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile, decide, reasons } from '../assets/js/bench-tripline.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const read = (p) => JSON.parse(readFileSync(root + p, 'utf8'));
const data = read('assets/data/bench-tripline.json');
const parity = read('assets/data/tripline-bench-parity.json');
const k = compile(data);

const bad = [];
const by = {};
for (const c of parity.cases) {
  const got = decide(k, c.i, c.c), why = reasons(got);
  const ok = JSON.stringify(got.s) === JSON.stringify(c.s) && JSON.stringify(got.r) === JSON.stringify(c.r)
    && why.stock === c.w[0] && why.custom === c.w[1];
  by[c.g] = by[c.g] || { n: 0, bad: 0 };
  by[c.g].n++;
  if (!ok) { by[c.g].bad++; bad.push({ group: c.g, image: c.i, cmd: c.c, expected: { s: c.s, r: c.r }, got }); }
}

// The recorded events shown on the page must carry the verdicts tripline computed, and the published totals.
const fixture = parity.cases.filter((c) => c.g === 'fixture');
if (fixture.length !== data.events.length) bad.push({ group: 'events', note: 'event count differs' });
data.events.forEach((e, i) => {
  const c = fixture[i];
  if (c.s[2] !== e.s || c.r[4] !== e.r || c.i !== e.i || !c.c.startsWith(e.c.replace(/\u2026$/, ''))) bad.push({ group: 'events', i, e, c });
});
const stockN = data.events.reduce((a, e) => a + e.s, 0), custN = data.events.reduce((a, e) => a + e.r, 0);
if (data.events.length !== 36 || stockN !== 0 || custN !== 2) bad.push({ group: 'totals', events: data.events.length, stockN, custN });

for (const [g, v] of Object.entries(by)) console.log(`${g.padEnd(8)} ${String(v.n).padStart(4)} cases, ${v.bad} differences`);
console.log(`events   36 recorded: stock ${stockN} flagged, replacement ${custN} flagged`);
if (bad.length) {
  console.log(JSON.stringify(bad.slice(0, 10), null, 1));
  console.log(`FAIL: ${bad.length} differences`);
  process.exit(1);
}
console.log(`OK: ${parity.cases.length} cases match tripline ${parity.meta.tripline} (${parity.meta.commit})`);
