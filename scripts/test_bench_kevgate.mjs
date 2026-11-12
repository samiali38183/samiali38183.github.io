// Consistency test for the kevgate "Control to evidence matrix". Reads files and runs Node only; it does not run kevgate.
//
//   node scripts/test_bench_kevgate.mjs            # stored data, live bench, static page
//   node scripts/test_bench_kevgate.mjs --fresh    # also runs `capture_kevgate_bench.py --check` (clones kevgate, needs gh and network)
//
// 1. The stored data (assets/data/kevgate-bench.json) is internally consistent: 12 to 16 controls, every control has a test or a CI
//    step, ranges are well formed, every cited CI step belongs to a successful run, every test has at least one case.
// 2. Everything the live bench shows (rows, filters, the detail panel of every control) equals the stored data. The module is mounted
//    on a small stub DOM and driven through its radio buttons and row buttons.
// 3. Everything the no-JS table in the built page shows equals the stored data.
// That the stored data equals a fresh capture from the repository and from GitHub is checked by `capture_kevgate_bench.py --check`.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
const data = JSON.parse(read(join(root, 'assets', 'data', 'kevgate-bench.json')));
const { rows, detail, mount, ref } = await import(pathToFileURL(join(root, 'assets', 'js', 'bench-kevgate.js')).href);

let checks = 0;
const failures = [];
function eq(label, got, want) {
  checks += 1;
  if (got !== want) failures.push(`${label}\n  got:  ${JSON.stringify(got).slice(0, 200)}\n  want: ${JSON.stringify(want).slice(0, 200)}`);
}
const ok = (label, cond) => eq(label, !!cond, true);
const plain = (s) => s.replace(/`/g, '');

// ---- 1. consistency of the stored data
const m = data.meta;
eq('tool, tag, commit', `${m.tool} ${m.tag} ${m.commit}`, 'kevgate v0.1.1 973c8c1');
ok('commit_full starts with commit', m.commit_full.startsWith(m.commit));
ok('12 to 16 controls', data.controls.length >= 12 && data.controls.length <= 16);
eq('277 tests collected', m.tests_total, 277);
eq('cited test cases all passed', m.test_cases_passed, m.test_cases_cited);
const layerIds = data.layers.map((l) => l.id);
const seen = new Set();
let citedTests = new Set(), stepCount = 0;
for (const c of data.controls) {
  ok(`${c.id}: unique id`, !seen.has(c.id)); seen.add(c.id);
  ok(`${c.id}: known layer`, layerIds.includes(c.layer));
  ok(`${c.id}: has a test or a CI step`, c.tests.length + c.ci.length > 0);
  ok(`${c.id}: has code, a threat and a limitation`, c.code.length > 0 && c.threat.text && c.limits.length > 0);
  for (const r of c.code.concat(c.ci.map((s) => s.src), c.ci.flatMap((s) => s.asserts), c.tests)) ok(`${c.id}: range ${r.path} ${r.start}-${r.end}`, r.start >= 1 && r.end >= r.start);
  for (const t of c.tests) { ok(`${c.id}: ${t.name} has cases`, t.cases >= 1); citedTests.add(t.id); }
  for (const s of c.ci) {
    stepCount += 1;
    ok(`${c.id}: ${s.step} succeeded in a successful run`, s.conclusion === 'success' && data.runs[s.wf].conclusion === 'success');
    ok(`${c.id}: step ${s.wf}/${s.n} is defined in a workflow file`, s.src.path === `.github/workflows/${s.wf}.yml`);
  }
}
eq('cited tests counted in meta', citedTests.size, m.tests_cited);
eq('cited cases counted in meta', [...citedTests].reduce((a, id) => a + data.controls.flatMap((c) => c.tests).find((t) => t.id === id).cases, 0), m.test_cases_cited);
for (const l of data.layers) ok(`layer ${l.id} has a control`, data.controls.some((c) => c.layer === l.id));
for (const [wf, r] of Object.entries(data.runs)) ok(`run ${wf} ${r.id} is a success`, r.conclusion === 'success');
const rel = data.controls.find((c) => c.registry).registry;
ok('registry: digest, anonymous pull and three attestation kinds', /^sha256:[0-9a-f]{64}$/.test(rel.digest) && rel.anonymous_pull && rel.attached.length === 3 && rel.sbom_components > 0);

// ---- 2. the live bench on a stub DOM
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.children = []; this.text = ''; this.handlers = {}; this.checked = false; this.className = ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'class') this.className = String(v); }
  appendChild(c) { this.children.push(c); return c; }
  get lastChild() { return this.children[this.children.length - 1]; }
  addEventListener(ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); }
  fire(ev, arg) { for (const fn of this.handlers[ev] || []) fn(arg); }
  set textContent(s) { this.children = []; this.text = String(s); }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }
  find(pred, out = []) { if (pred(this)) out.push(this); for (const c of this.children) if (c.find) c.find(pred, out); return out; }
}
const doc = { createElement: (t) => new El(t), createTextNode: (s) => { const e = new El('#text'); e.text = s; return e; } };
const rootEl = new El('div');
mount(doc, rootEl, data);
const cls = (c) => (e) => e.className.split(' ').includes(c);
const radios = rootEl.find((e) => e.tag === 'input');
eq('live bench has one radio per layer plus All', radios.length, data.layers.length + 1);
const status = () => rootEl.find((e) => e.attrs.role === 'status')[0].textContent;
const pickLayer = (v) => { const r = radios.find((x) => x.attrs.value === v); radios.forEach((x) => { x.checked = false; }); r.checked = true; r.fire('change'); };
const tbody = () => rootEl.find((e) => e.tag === 'tbody')[0];
const pickRows = () => tbody().children.filter((tr) => !cls('kg-row')(tr));

for (const layer of ['all', ...layerIds]) {
  pickLayer(layer);
  const want = rows(data, layer);
  eq(`live ${layer}: row count`, pickRows().length, data.controls.filter((c) => layer === 'all' || c.layer === layer).length);
  eq(`live ${layer}: row titles`, pickRows().map((tr) => tr.children[0].textContent).join('|'), want.map((r) => r.title).join('|'));
  eq(`live ${layer}: evidence counts`, pickRows().map((tr) => [2, 3, 4].map((i) => tr.children[i].textContent).join('/')).join('|'),
    want.map((r) => `${r.code}/${r.tests}/${r.ci}`).join('|'));
  ok(`live ${layer}: status says the control count`, status().includes(`${want.length} control`));
}
pickLayer('all');
for (const c of data.controls) {
  const btn = pickRows().map((tr) => tr.children[0].children[0]).find((b) => b.textContent === c.title);
  btn.fire('click');
  const L = `live ${c.id}`;
  const panel = rootEl.find(cls('kg-detail'))[0];
  ok(`${L}: panel opens`, panel);
  eq(`${L}: only one panel`, rootEl.find(cls('kg-detail')).length, 1);
  const txt = plain(panel.textContent), d = detail(data, c);
  const links = panel.find((e) => e.tag === 'a').map((a) => [a.textContent, a.attrs.href]);
  eq(`${L}: title`, panel.find((e) => e.tag === 'h2')[0].textContent, c.title);
  ok(`${L}: threat text`, txt.includes(plain(c.threat.text)));
  for (const l of c.limits) ok(`${L}: limitation text`, txt.includes(plain(l.text)));
  for (const x of c.code) ok(`${L}: code ${ref(data, x).text}`, links.some((k) => k[0] === ref(data, x).text && k[1] === ref(data, x).href));
  for (const t of c.tests) ok(`${L}: test ${t.name}`, txt.includes(t.path + '::' + t.name + (t.cases > 1 ? ` (${t.cases} cases)` : '')));
  for (const s of c.ci) {
    ok(`${L}: CI step ${s.step}`, txt.includes(`${s.wf} / ${s.job} / step ${s.n}: ${s.step}`));
    ok(`${L}: job link`, links.some((k) => k[1] === `${m.repo}/actions/runs/${data.runs[s.wf].id}/job/${s.job_id}`));
    ok(`${L}: run chip`, txt.includes(`run ${data.runs[s.wf].id} passed ${data.runs[s.wf].date}`));
  }
  if (c.registry) ok(`${L}: registry text`, txt.includes(c.registry.digest) && txt.includes(`${c.registry.sbom_components} components`));
  eq(`${L}: tests heading only with tests`, txt.includes('Evidence: tests'), c.tests.length > 0);
  ok(`${L}: expanded button says so`, pickRows().some((tr) => tr.children[0].children[0].attrs['aria-expanded'] === 'true'));
  ok(`${L}: status names the open control`, status().includes('Detail open for ' + c.title));
  ok(`${L}: model equals the data`, d.threat.text === c.threat.text && d.ci.length === c.ci.length);
}
// closing, toggling and filtering away
const first = () => pickRows()[0].children[0].children[0];
first().fire('click'); first().fire('click');
eq('clicking an open control closes it', rootEl.find(cls('kg-detail')).length, 0);
first().fire('click'); rootEl.fire('keydown', { key: 'Escape' });
eq('Escape closes the panel', rootEl.find(cls('kg-detail')).length, 0);
first().fire('click'); pickLayer('cloud');
eq('filtering the open control away closes the panel', rootEl.find(cls('kg-detail')).length, 0);

// ---- 3. the no-JS fallback in the built page
const page = read(join(root, 'projects', 'kevgate', 'index.html'));
const unesc = (s) => s.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const trs = [...page.matchAll(/<tr data-control="([^"]+)">([\s\S]*?)<\/tr>/g)];
eq('static table has a row per control', trs.length, data.controls.length);
for (const c of data.controls) {
  const tr = trs.find((x) => x[1] === c.id);
  ok(`static ${c.id}: row exists`, tr);
  if (!tr) continue;
  const raw = tr[2], t = unesc(raw);
  ok(`static ${c.id}: title and layer`, t.includes(c.title) && t.includes(data.layers.find((l) => l.id === c.layer).label));
  ok(`static ${c.id}: threat`, t.includes(plain(c.threat.text)));
  for (const l of c.limits) ok(`static ${c.id}: limitation`, t.includes(plain(l.text)));
  for (const x of c.code) ok(`static ${c.id}: code ${ref(data, x).text}`, raw.includes(`href="${ref(data, x).href}">${ref(data, x).text}</a>`));
  for (const x of c.tests) ok(`static ${c.id}: test ${x.name}`, t.includes(x.path + '::' + x.name + (x.cases > 1 ? ` (${x.cases} cases)` : '')));
  for (const s of c.ci) {
    ok(`static ${c.id}: CI step ${s.step}`, t.includes(`${s.wf} / ${s.job} / step ${s.n}: ${s.step}`));
    ok(`static ${c.id}: run chip`, t.includes(`run ${data.runs[s.wf].id} passed ${data.runs[s.wf].date}`));
  }
  if (c.registry) ok(`static ${c.id}: registry`, t.includes(c.registry.digest) && t.includes(`${c.registry.sbom_components} components`));
}
ok('page loads the module and stylesheet', page.includes('<script type="module" src="/assets/js/bench-kevgate.js"></script>') && page.includes('/assets/css/bench-kevgate.css'));
ok('page has the static and live regions', page.includes('class="bench-static"') && page.includes('data-bench="kevgate"') && page.includes('data-bench-mount'));
ok('page says what the matrix is and what evidence means', page.includes('It does not evaluate anything in the browser') && page.includes('What evidence means here') && page.includes('not an audit'));
ok('caption gives tag, commit and counts', [m.tag, m.commit, `Python ${m.python}`, `pytest ${m.pytest}`, `${m.tests_cited} cited tests`, `${m.test_cases_cited} cases`].every((x) => page.includes(x)));
ok('deployment plate has two labelled SVGs', (page.match(/<svg viewBox="[^"]+" role="img" aria-labelledby="kgarch\d-t kgarch\d-d">/g) || []).length === 2);
for (const name of ['kevgate-client=true', 'NetworkPolicy kevgate', 'Service kevgate', 'Pod kevgate', 'Volume kevgate-data', 'release, on a version tag']) ok(`plate names ${name}`, page.includes(name));
const text = page.replace(/<(script|style|pre|svg)[\s\S]*?<\/\1>/g, ' ').replace(/<[^>]+>/g, ' ');
ok('no first-person wording and no tool-authorship wording in the page text', !/\b(I|my|me|we|our)\b/.test(text) && !/\b(AI|Claude|LLM|ChatGPT|assistant)\b/.test(text));

if (process.argv.includes('--fresh')) {
  const args = [join(root, 'scripts', 'capture_kevgate_bench.py'), '--check'];
  if (process.env.KG_CLONE) args.push('--clone', process.env.KG_CLONE);
  if (process.env.KG_VENV) args.push('--venv', process.env.KG_VENV);
  const r = spawnSync(process.env.PYTHON || 'python', args, { encoding: 'utf8' });
  const last = (r.stdout || '').trim().split('\n').pop();
  eq('capture --check against a fresh capture', r.status === 0 && last.endsWith('OK'), true);
  console.log(last || r.stderr);
}

if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nFAILED: ${failures.length} of ${checks} checks`);
  process.exit(1);
}
console.log(`bench-kevgate consistency: ${checks} checks passed (${data.controls.length} controls, live bench on a stub DOM, static table, deployment plate)`);
