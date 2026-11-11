// Parity and consistency test for the fuzzdiff "Side-by-side parser" bench. Runs nothing but Node and reads files;
// it does not run any parser. To check the data against fresh parser runs use
// `python scripts/capture_fuzzdiff_bench.py --check`.
//
//   node scripts/test_bench_fuzzdiff.mjs [path/to/data.json]     (the optional path is for the mutation check in docs/QC.md)
//
// 1. The data is internally consistent: byte counts match the escaped bytes, every harness classification agrees with the
//    two results it classifies (Equal means identical, BothReject means both errors, RustStricter(D1) needs a fold and
//    strict mode, Divergence is only for the seeded bugs), and every outcome pattern (C, P, R letters and "!") agrees with
//    the verdicts and fields recorded for the three parsers.
// 2. The data agrees with docs/DIFFERENTIAL_HTTPARSE.md: for each curated input the bytes, the three verdicts, the pattern and
//    the Stricter column equal the row of the document's curated table (a verbatim copy in assets/data/fuzzdiff-bench/), and
//    the sweep totals add up.
// 3. The seeded-bug table has the five names and the detection counts the repository's README prints for this run.
// 4. Everything the live bench displays (module mounted on a stub DOM, every input picked through its radio buttons) equals
//    the text built from the data, and everything the no-JS fallback in the built page displays equals the live bench.
// 5. The seeded-bug panel on the built page shows the recorded counts and a strip whose tick count follows the counts.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
const dataPath = process.argv[2] || join(root, 'assets', 'data', 'fuzzdiff-bench.json');
const data = JSON.parse(read(dataPath));
const { model, mount, resultLines, shownBytes } = await import(pathToFileURL(join(root, 'assets', 'js', 'bench-fuzzdiff.js')).href);

let checks = 0;
const failures = [];
function eq(label, got, want) {
  checks += 1;
  if (got !== want) failures.push(`${label}\n  got:  ${JSON.stringify(got).slice(0, 200)}\n  want: ${JSON.stringify(want).slice(0, 200)}`);
}
function ok(label, cond) { eq(label, !!cond, true); }

/* "\r\n\x80\\" style escapes (as written by the capture program and by the document) back to bytes */
function unescape(s) {
  const out = [];
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c !== '\\') { out.push(s.charCodeAt(i)); continue; }
    const n = s[++i];
    if (n === 'r') out.push(13); else if (n === 'n') out.push(10); else if (n === 't') out.push(9);
    else if (n === '\\') out.push(92); else if (n === '"') out.push(34);
    else if (n === 'x') { out.push(parseInt(s.slice(i + 1, i + 3), 16)); i += 2; }
    else throw new Error('bad escape \\' + n + ' in ' + s.slice(0, 60));
  }
  return out.join(',');
}
const word = { complete: 'C', partial: 'P', error: 'R', panic: 'R' };
const wordName = { complete: 'complete', partial: 'partial', error: 'reject', panic: 'reject' };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const core = (r) => ({ consumed: r.consumed, method: r.method, target: r.target, minor: r.minor, status: r.status, reason: r.reason, headers: r.headers, nheaders: r.nheaders });

// ---- 1. internal consistency
const ids = new Set();
for (const i of data.inputs) {
  ids.add(i.id);
  eq(`${i.id}: bytes_len equals the escaped bytes`, unescape(i.bytes).split(',').length, i.bytes_len);
  ok(`${i.id}: every parser result present or intentionally absent`, i.c && i.rust && (i.httparse || i.op === 'chunked'));
  const cl = resultLines(i.c, i.op), rl = resultLines(i.rust, i.op);
  const h = i.harness;
  if (h.kind === 'Equal') {
    eq(`${i.id}: Equal means C and Rust show the same result`, same(cl, rl), true);
    ok(`${i.id}: Equal is not an error`, i.c.verdict !== 'error');
  } else if (h.kind === 'BothReject') {
    eq(`${i.id}: BothReject C`, i.c.verdict, 'error');
    eq(`${i.id}: BothReject Rust`, i.rust.verdict, 'error');
  } else if (h.kind === 'RustStricter') {
    eq(`${i.id}: deviation is D1`, h.deviation, 'D1');
    ok(`${i.id}: D1 only in strict mode`, i.strict);
    ok(`${i.id}: C accepted`, i.c.verdict !== 'error');
    eq(`${i.id}: Rust says ObsFold`, i.rust.error, 'ObsFold');
    ok(`${i.id}: D1 needs a line feed followed by SP or HTAB`, /\\n[ \\t]/.test(i.bytes.replace(/\\\\/g, '')));
  } else {
    eq(`${i.id}: Divergence is only for the seeded bugs`, i.group, 'Planted bug');
    ok(`${i.id}: a named seeded bug`, i.mutant);
    ok(`${i.id}: results differ`, !same(cl, rl));
    eq(`${i.id}: RustPanic iff Rust panicked`, h.how === 'RustPanic', i.rust.verdict === 'panic');
  }
  if (!i.strict && !i.mutant) {
    ok(`${i.id}: has a pattern`, i.pattern);
    const hp = i.httparse;
    if (hp) {
      const letters = word[i.c.verdict] + word[i.rust.verdict] + word[hp.verdict];
      eq(`${i.id}: pattern letters follow the three verdicts`, i.pattern.slice(0, 3), letters);
      if (i.op !== 'chunked') {
        const allDone = [i.c, i.rust, hp].every((r) => r.verdict === 'complete');
        const fieldsDiffer = allDone && !(same(core(i.c), core(i.rust)) && same(core(i.c), core(hp)));
        eq(`${i.id}: "!" iff all complete with different fields`, i.pattern.endsWith('!'), fieldsDiffer);
      }
    }
    if (i.pattern.slice(0, 3) === 'CCC' || i.pattern.slice(0, 3) === 'RRR' || i.pattern.slice(0, 3) === 'PPP') {
      if (!i.pattern.endsWith('!') && i.op !== 'chunked') eq(`${i.id}: all-agree pattern has explained_by agree`, i.explained_by, 'agree');
    } else if (i.op !== 'chunked') {
      ok(`${i.id}: a disagreement is explained`, i.explained_by && i.explained_by !== 'agree');
    }
  }
  if (i.strict) eq(`${i.id}: strict input uses the default-configuration pattern of its curated twin`, i.pattern, data.inputs.find((x) => x.id === 'obs-fold').pattern);
}
eq('ids unique', ids.size, data.inputs.length);
eq('number of inputs', data.inputs.length, 19);
eq('seeded-bug rows', data.inputs.filter((i) => i.mutant).map((i) => i.mutant).join(','), 'HeaderLenOffByOne,MissingBoundsCheck');
eq('meta tag and commit', data.meta.tag + ' ' + data.meta.commit, 'v0.2.0 6ec1e6e');

// ---- 2. the document
const curated = read(join(root, 'assets', 'data', 'fuzzdiff-bench', 'curated-table.md'));
const rows = curated.split('\n').filter((l) => l.startsWith('| ') && !l.includes('---')).map((l) => l.replace(/^\| /, '').replace(/ \|$/, '').split(' | '));
eq('curated table has 86 example rows plus the header', rows.length, 87);
for (const i of data.inputs.filter((x) => x.doc)) {
  const d = i.doc;
  const hit = rows.filter((r) => r[0] === d.class && r[1].endsWith('(' + d.label + ')'));
  eq(`${i.id}: one document row`, hit.length, 1);
  const r = hit[0];
  if (!r) continue;
  const m = /^`(.*)` \(/.exec(r[1]);
  eq(`${i.id}: bytes equal the document example`, unescape(m[1]), unescape(i.bytes));
  eq(`${i.id}: pattern equals the document`, i.pattern, r[5]);
  eq(`${i.id}: doc.pattern`, d.pattern, r[5]);
  eq(`${i.id}: Stricter equals the document`, d.stricter, r[6]);
  eq(`${i.id}: C verdict equals the document`, wordName[i.c.verdict], r[2]);
  eq(`${i.id}: httparse verdict equals the document`, wordName[i.httparse.verdict], r[4]);
  if (!i.strict) eq(`${i.id}: Rust verdict equals the document`, wordName[i.rust.verdict], r[3]);
  // the Stricter column follows from the pattern
  const [pc, , ph] = r[5];
  const expect = r[5].endsWith('!') ? 'same verdict, fields differ'
    : pc === ph ? 'same'
    : (pc === 'P' && ph === 'R') ? 'httparse (rejects earlier)'
    : ph === 'R' ? 'httparse' : 'picohttpparser';
  eq(`${i.id}: Stricter follows from the pattern ${r[5]}`, r[6], expect);
}
const sweep = read(join(root, 'assets', 'data', 'fuzzdiff-bench', 'sweep-table.md'));
const total = [...sweep.split('Disagreements by attributed feature.')[0].matchAll(/^\| \w+ \| [CPR!]+ \| (\d+) \|$/gm)].reduce((a, m) => a + Number(m[1]), 0);
eq('entry-point table sums to the disagreement total', String(total), /they disagreed on (\d+)\./.exec(sweep)[1]);
eq('picohttpparser and fuzzdiff never differ in the sweep', /differed on (\d+) inputs/.exec(sweep)[1], '0');
eq('no unexplained disagreement in the sweep', /explained by no known feature: (\d+)/.exec(sweep)[1], '0');

// ---- 3. seeded bugs (the numbers the repository README prints for the 2026-11-11 run; counts are deterministic)
const want = { HeaderLenOffByOne: 3, MissingBoundsCheck: 286, WrongStateAfterCrlf: 8, OverheadRatio: null, StatusGuard: 10085 };
eq('five seeded bugs', data.mutants.map((m) => m.name).join(','), Object.keys(want).join(','));
for (const m of data.mutants) {
  eq(`${m.name}: generator inputs equal the README`, m.generator_inputs, want[m.name]);
  ok(`${m.name}: caught by the generator or a targeted case`, m.generator_inputs !== null || m.targeted_case !== null);
}
eq('OverheadRatio is caught by targeted case 1', data.mutants[3].targeted_case, 1);
eq('StatusGuard is also caught by targeted case 4', data.mutants[4].targeted_case, 4);
ok('MissingBoundsCheck first failing input is the one in the README', data.mutants[1].first_failing_input.includes('GET /q=0.9&;;q=0.9 HTTP/1.1') && data.mutants[1].first_failing_input.includes('max_headers=2'));
eq('control inputs', data.control.inputs, 500000);
eq('control divergences', data.control.divergences, 0);

// ---- 4a. the live bench on a stub DOM
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.children = []; this.text = ''; this.handlers = {}; this.checked = false; this.hidden = false; this.className = ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'class') this.className = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); }
  fire(ev) { for (const fn of this.handlers[ev] || []) fn(); }
  set textContent(s) { this.children = []; this.text = String(s); }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }
  find(pred, out = []) { if (pred(this)) out.push(this); for (const c of this.children) c.find ? c.find(pred, out) : 0; return out; }
}
const doc = { createElement: (t) => new El(t), createTextNode: (s) => { const e = new El('#text'); e.text = s; return e; } };
const rootEl = new El('div');
mount(doc, rootEl, data);
const cls = (c) => (e) => e.className.split(' ').includes(c);
const radios = rootEl.find((e) => e.tag === 'input');
eq('one radio button per input', radios.length, data.inputs.length);
eq('radios share one name (one keyboard group)', new Set(radios.map((r) => r.attrs.name)).size, 1);
eq('radio groups by entry point', rootEl.find((e) => e.tag === 'legend').map((e) => e.textContent).join('|'), 'Request line|Headers|Response|Chunked body|Truncated input|Planted bug');
const liveCols = () => rootEl.find((e) => e.attrs['data-col']).map((c) => ({ name: c.find((e) => e.tag === 'h4')[0].textContent, lines: c.find((e) => e.tag === 'p').map((p) => p.textContent) }));
const stamp = () => rootEl.find(cls('stamp'))[0];
const bytesEl = () => rootEl.find(cls('fz-bytes'))[0].find((e) => e.tag === 'code')[0].textContent;
const rel = () => rootEl.find(cls('fz-rel'))[0];
const status = () => rootEl.find((e) => e.attrs.role === 'status')[0].textContent;
const live = {};
for (const i of data.inputs) {
  const r = radios.find((x) => x.attrs.value === i.id);
  r.checked = true; r.fire('change');
  const m = model(data, i.id);
  const cols = liveCols();
  eq(`live ${i.id}: three columns`, cols.length, 3);
  const direct = [i.c, i.rust, i.httparse].map((x) => resultLines(x, i.op));
  cols.forEach((c, n) => eq(`live ${i.id}: column ${n} equals the recorded result`, c.lines.join('\n'), direct[n].join('\n')));
  eq(`live ${i.id}: bytes`, bytesEl(), shownBytes(i).text);
  eq(`live ${i.id}: stamp text`, stamp().textContent, m.stamp[1]);
  eq(`live ${i.id}: stamp text names the recorded classification`, stamp().textContent.split(' ')[0], i.harness.kind);
  eq(`live ${i.id}: relation`, rel().textContent, m.relation);
  eq(`live ${i.id}: status line`, status(), m.spoken);
  // recorded facts appear in what is displayed
  for (const [r, c] of [[i.c, 0], [i.rust, 1], [i.httparse, 2]]) {
    if (!r) continue;
    const text = cols[c].lines.join('\n');
    if (r.verdict === 'complete' && 'consumed' in r) ok(`live ${i.id}: col ${c} shows consumed ${r.consumed}`, text.includes('consumed ' + r.consumed) || text.includes('size line ' + r.consumed));
    if (r.error) ok(`live ${i.id}: col ${c} shows error ${r.error}`, text.includes(r.error));
    if (r.method) ok(`live ${i.id}: col ${c} shows method and target`, text.includes('"' + r.method + '"') && text.includes('"' + r.target + '"'));
  }
  live[i.id] = { cols: cols.map((c) => c.lines.join('\n')), bytes: bytesEl(), stamp: stamp().textContent, rel: rel().textContent };
}

// ---- 4b. the no-JS fallback in the built page
const page = read(join(root, 'projects', 'fuzzdiff', 'index.html'));
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const trs = [...page.matchAll(/<tr data-fz-id="([^"]+)">([\s\S]*?)<\/tr>/g)];
eq('static table has one row per input', trs.length, data.inputs.length);
for (const [, id, body] of trs) {
  const cell = (k) => { const m = new RegExp('data-fz="' + k + '"[^>]*>([\\s\\S]*?)</(?:td|code|p|span)>').exec(body); return m ? unesc(m[1].replace(/<br>/g, '\n')) : null; };
  const L = live[id];
  ok(`static ${id}: is a known input`, L);
  if (!L) continue;
  eq(`static ${id}: C column equals the live bench`, cell('c'), L.cols[0]);
  eq(`static ${id}: Rust column equals the live bench`, cell('rust'), L.cols[1]);
  eq(`static ${id}: httparse column equals the live bench`, cell('hp'), L.cols[2]);
  eq(`static ${id}: bytes equal the live bench`, cell('bytes'), L.bytes);
  eq(`static ${id}: relation equals the live bench`, cell('relation'), L.rel);
  ok(`static ${id}: stamp text equals the live bench`, body.includes('>' + unesc(L.stamp).replace(/&/g, '&amp;') + '</span>'));
}
ok('page loads the bench module and style', page.includes('<script type="module" src="/assets/js/bench-fuzzdiff.js"></script>') && page.includes('/assets/css/bench-fuzzdiff.css'));
ok('page has the static and live regions', page.includes('class="bench-static"') && page.includes('data-bench-mount') && page.includes('data-bench="fuzzdiff"'));
ok('caption gives the tag, commit and tool versions', page.includes('tag ' + data.meta.tag) && page.includes('commit ' + data.meta.commit) && page.includes('httparse ' + data.meta.httparse));

// ---- 5. the seeded-bug panel
const fmt = (n) => n.toLocaleString('en-US');
for (const m of data.mutants) {
  const row = new RegExp('<tr data-mutant="' + m.name + '">([\\s\\S]*?)</tr>').exec(page);
  ok(`panel ${m.name}: row present`, row);
  if (!row) continue;
  const cells = [...row[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((c) => unesc(c[1]));
  eq(`panel ${m.name}: generator inputs`, cells[0], m.generator_inputs === null ? 'not caught in ' + fmt(m.budget) : fmt(m.generator_inputs));
  eq(`panel ${m.name}: targeted case`, cells[2], m.targeted_case ? 'case ' + m.targeted_case : 'none catches it');
  eq(`panel ${m.name}: how it showed`, cells[3], m.generator_how || m.targeted_how);
  const strip = new RegExp('aria-label="' + m.name + ', (\\d+) half-decades of inputs: ([^"]*)"').exec(page);
  ok(`panel ${m.name}: strip present`, strip);
  if (strip) {
    const full = Math.ceil(2 * Math.log10(m.budget));
    eq(`panel ${m.name}: strip has the full budget in ticks`, Number(strip[1]), full);
    const first = Number(/^(\d+) /.exec(strip[2])[1]);
    eq(`panel ${m.name}: strip ticks follow the count`, first, m.generator_inputs === null ? full : Math.max(1, Math.ceil(2 * Math.log10(m.generator_inputs))));
    eq(`panel ${m.name}: strip words`, /(half-decades searched|until the harness caught)/.test(strip[2]), true);
  }
}
ok('panel shows the control run', page.includes(fmt(data.control.inputs) + ' inputs') && page.includes(data.control.divergences + ' divergences'));
// the sweep numbers on the page
for (const n of ['2,000,000', '1,390,722', '609,278', '36,905', '258,293']) ok(`page shows sweep number ${n}`, page.includes(n));

if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nFAILED: ${failures.length} of ${checks} checks`);
  process.exit(1);
}
console.log(`bench-fuzzdiff parity: ${checks} checks passed (${data.inputs.length} inputs, ${rows.length - 1} document rows, ${data.mutants.length} seeded bugs, live bench and static fallback)`);
