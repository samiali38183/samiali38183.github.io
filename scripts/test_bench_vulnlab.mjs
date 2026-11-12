// Consistency test for the vulnlab "Lab explorer". Runs nothing but Node and reads files; it does not run vulnlab.
//
//   node scripts/test_bench_vulnlab.mjs            # stored data, live bench, static page
//   node scripts/test_bench_vulnlab.mjs --fresh    # also runs `capture_vulnlab_bench.py --check` (clones vulnlab, needs Python 3.12)
//
// 1. The stored data (assets/data/vulnlab-bench.json) is internally consistent: test counts add up and all pass, sinkline findings
//    agree with the recorded text and exit status, replay counts agree with the recorded replay output, marked lines exist, and no
//    request string or address of an attack log is in the file.
// 2. Everything the live bench displays (code, tests, sinkline output, replay) for all six lab and version pairs equals the stored data.
//    The module is mounted on a small stub DOM and driven through its radio buttons.
// 3. Everything the no-JS fallback in the built page displays equals the stored data.
// That the stored data equals a fresh run of the real tools is checked by `python scripts/capture_vulnlab_bench.py --check`.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
const raw = read(join(root, 'assets', 'data', 'vulnlab-bench.json'));
const data = JSON.parse(raw);
const { model, mount } = await import(pathToFileURL(join(root, 'assets', 'js', 'bench-vulnlab.js')).href);

let checks = 0;
const failures = [];
function eq(label, got, want) {
  checks += 1;
  if (got !== want) failures.push(`${label}\n  got:  ${JSON.stringify(got).slice(0, 160)}\n  want: ${JSON.stringify(want).slice(0, 160)}`);
}
const ok = (label, cond) => eq(label, !!cond, true);

// ---- 1. consistency of the stored data
const pv = data.provenance;
eq('tool and tag', `${pv.tool} ${pv.tag} ${pv.commit}`, 'vulnlab v0.1.1 dd2665d');
eq('commit_full starts with commit', pv.commit_full.startsWith(pv.commit), true);
eq('three labs', data.labs.length, 3);
let labTests = 0;
for (const lab of data.labs) {
  eq(`${lab.id}: two versions`, lab.versions.map((v) => v.id).join(','), 'vulnerable,fixed');
  for (const v of lab.versions) {
    const where = `${lab.id}/${v.id}`;
    const lines = v.code.replace(/\n$/, '').split('\n');
    for (const t of v.tests) {
      labTests += t.passed;
      ok(`${where}: ${t.name} passed all ${t.cases} cases`, t.passed === t.cases && t.cases >= 1);
      ok(`${where}: ${t.name} has a role`, data.roles[t.role]);
    }
    for (const n of v.marks.bug.concat(v.marks.changed)) ok(`${where}: marked line ${n} exists`, n >= 1 && n <= lines.length);
    eq(`${where}: bug lines only on the vulnerable version`, v.marks.bug.length, v.id === 'vulnerable' ? 1 : 0);
    eq(`${where}: changed lines only on the fixed version`, v.marks.changed.length > 0, v.id === 'fixed');
    const s = v.sinkline;
    const textFound = /^\[(CRITICAL|HIGH|MEDIUM|LOW)\] SL-/m.test(s.out);
    eq(`${where}: sinkline findings agree with the text`, s.findings.length > 0, textFound);
    eq(`${where}: sinkline findings counted in the summary line`, s.out.includes(`${s.findings.length} finding(s)`), true);
    eq(`${where}: sinkline reading`, s.reading, v.id === 'vulnerable' ? (s.findings.length ? 'true positive' : 'missed') : (s.findings.length ? 'false positive' : 'clean'));
    for (const f of s.findings) {
      ok(`${where}: text names ${f.rule_id}, ${f.cwe} and line ${f.line}`, s.out.includes(f.rule_id) && s.out.includes(f.cwe) && s.out.includes(`app.py:${f.line}`));
      for (const st of f.flow) ok(`${where}: flow line ${st.line} exists`, st.line <= lines.length);
    }
    ok(`${where}: no mojibake in the sinkline output`, !/â\u0094|â\u0080/.test(s.out));
  }
  const d = lab.detection;
  for (const k of ['attack', 'benign']) {
    const r = d[k];
    ok(`${lab.id}: ${k} replay output starts with its counts`, r.out.startsWith(`sample_${k}.ndjson: ${r.events} events, ${r.alerts} alert(s)\n`));
    eq(`${lab.id}: ${k} matching count list`, r.matching.length, r.alerts);
  }
  ok(`${lab.id}: attack alerts, benign does not`, d.attack.alerts >= 1 && d.benign.alerts === 0);
  eq(`${lab.id}: sample sources`, d.attack.from + ',' + d.benign.from, 'vulnerable,fixed');
  eq(`${lab.id}: detection test passed`, d.test.passed, d.test.cases);
  labTests += d.test.passed;
}
eq('lab tests add up with the safety tests to the total', labTests + pv.totals.safety_tests, pv.totals.passed);
eq('lab tests', labTests, pv.totals.lab_tests);
eq('137 passed', pv.totals.passed, 137);
eq('lab 03 correlation: 5 or more in 1m by session', JSON.stringify(data.labs[2].detection.correlation), JSON.stringify({ type: 'value_count', group_by: 'session', timespan: '1m', gte: 5, field: 'object_id' }));
eq('lab 01 and 02 have no correlation', data.labs[0].detection.correlation === null && data.labs[1].detection.correlation === null, true);
eq('sinkline summary: findings per version', data.labs.map((l) => l.versions.map((v) => v.sinkline.findings.length).join('/')).join(' '), '1/1 1/1 0/0');
// safety: attack request strings and logs are not stored
for (const bad of ['sort=', 'url=http', 'CASE WHEN', 'api_keys', '169.254.', '/latest/meta-data']) ok(`data does not contain ${JSON.stringify(bad)}`, !raw.includes(bad));

// ---- 2. the live bench on a stub DOM
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.children = []; this.text = ''; this.handlers = {}; this.checked = false; this.className = ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'class') this.className = String(v); }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); }
  fire(ev) { for (const fn of this.handlers[ev] || []) fn(); }
  set textContent(s) { this.children = []; this.text = String(s); }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }
  find(pred, out = []) { if (pred(this)) out.push(this); for (const c of this.children) if (c.find) c.find(pred, out); return out; }
}
const doc = { createElement: (t) => new El(t), createTextNode: (s) => { const e = new El('#text'); e.text = s; return e; } };
const rootEl = new El('div');
mount(doc, rootEl, data);
const cls = (c) => (e) => e.className.split(' ').includes(c);
const radios = rootEl.find((e) => e.tag === 'input');
const pick = (name, value) => { const r = radios.find((x) => x.attrs.name === name && x.attrs.value === value); r.checked = true; r.fire('change'); };
eq('live bench has 3 + 2 radio buttons', radios.length, 5);
for (const lab of data.labs) {
  for (const v of lab.versions) {
    pick('vl-lab', lab.id); pick('vl-ver', v.id);
    const L = `live ${lab.id}/${v.id}`;
    const codePre = rootEl.find(cls('vl-code'))[0];
    const shownCode = codePre.find(cls('c')).map((e) => e.textContent).join('\n') + '\n';
    eq(`${L}: code pane equals the stored source`, shownCode, v.code);
    eq(`${L}: code pane label`, codePre.attrs['data-label'], v.file);
    const gut = codePre.find(cls('d')).map((e, i) => [i + 1, e.textContent]).filter((x) => x[1]).map((x) => x.join(':'));
    const want = v.marks.bug.map((n) => n + ':!').concat(v.marks.changed.map((n) => n + ':+')).sort((a, b) => parseInt(a) - parseInt(b));
    eq(`${L}: gutter marks`, gut.join(','), want.join(','));
    const flow = new Set(v.sinkline.findings.flatMap((f) => f.flow.map((s) => `${s.line}:${s.kind}`)));
    const tagged = new Set(codePre.find(cls('l')).flatMap((l, i) => l.find((e) => e.className.startsWith('k k-') && e.className !== 'k k-bug').map((e) => `${i + 1}:${e.className.slice(4)}`)));
    eq(`${L}: route tags equal the recorded sinkline path`, [...tagged].sort().join(','), [...flow].sort().join(','));
    eq(`${L}: sinkline output pane`, rootEl.find(cls('vl-sink'))[0].find((e) => e.tag === 'code')[0].textContent, v.sinkline.out);
    eq(`${L}: sinkline pane label`, rootEl.find(cls('vl-sink'))[0].attrs['data-label'], '$ ' + v.sinkline.command);
    eq(`${L}: replay pane`, rootEl.find(cls('vl-replay'))[0].find((e) => e.tag === 'code')[0].textContent, lab.detection.attack.out + lab.detection.benign.out);
    const trows = rootEl.find(cls('vl-tests'))[0].find((e) => e.tag === 'tbody')[0].children;
    eq(`${L}: test rows`, trows.map((r) => r.children[0].textContent).join('|'), v.tests.map((t) => t.name).join('|'));
    eq(`${L}: test results`, trows.map((r) => r.children[2].textContent).join('|'), v.tests.map((t) => (t.cases > 1 ? `Pass (${t.passed} of ${t.cases} cases)` : 'Pass')).join('|'));
    const stamps = rootEl.find(cls('stamp')).map((e) => e.textContent);
    eq(`${L}: first stamp`, stamps[0], v.id === 'vulnerable' ? 'Impact demonstrated' : 'Impact blocked');
    ok(`${L}: sinkline stamp`, stamps.includes(v.sinkline.findings.length ? 'Finding' : 'No finding'));
    const drows = rootEl.find(cls('vl-det'))[0].find((e) => e.tag === 'tbody')[0].children;
    eq(`${L}: detection rows`, drows.map((r) => r.children[1].textContent).join('|'),
      ['attack', 'benign'].map((k) => `${lab.detection[k].events} events, ${lab.detection[k].alerts} alert${lab.detection[k].alerts === 1 ? '' : 's'}`).join('|'));
    ok(`${L}: status line says the sinkline result`, rootEl.find((e) => e.attrs.role === 'status')[0].textContent.includes(v.sinkline.findings.length ? 'sinkline: finding' : 'sinkline: no finding'));
    eq(`${L}: model output is the stored capture`, model(data, lab.id, v.id).sink.out, v.sinkline.out);
  }
}

// ---- 3. the no-JS fallback in the built page
const page = read(join(root, 'projects', 'vulnlab', 'index.html'));
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const secs = [...page.matchAll(/<section class="vl-sv" data-lab="([^"]+)" data-ver="([^"]+)"[^>]*>([\s\S]*?)<\/section>/g)];
eq('static page has 6 version blocks and 3 detection blocks', secs.length, 9);
const pres = (html) => [...html.matchAll(/<pre data-label="([^"]*)" tabindex="0"><code>([\s\S]*?)<\/code><\/pre>/g)].map((m) => ({ label: unesc(m[1]), body: unesc(m[2]) }));
for (const lab of data.labs) {
  for (const v of lab.versions) {
    const S = `static ${lab.id}/${v.id}`;
    const blk = secs.find((m) => m[1] === lab.id && m[2] === v.id);
    ok(`${S}: block exists`, blk);
    if (!blk) continue;
    const p = pres(blk[3]);
    eq(`${S}: two code blocks`, p.length, 2);
    eq(`${S}: source label`, p[0].label, v.file);
    eq(`${S}: source equals the stored source`, p[0].body, v.code);
    eq(`${S}: sinkline label`, p[1].label, '$ ' + v.sinkline.command);
    eq(`${S}: sinkline output equals the capture`, p[1].body, v.sinkline.out);
    for (const t of v.tests) ok(`${S}: lists test ${t.name}`, blk[3].includes(`<code>${t.name}</code>`));
    ok(`${S}: shows the same reading text as the live bench`, unesc(blk[3]).includes(model(data, lab.id, v.id).sink.reading));
    ok(`${S}: names the bug line`, v.marks.bug.every((n) => blk[3].includes(`names: ${n}.`)));
    ok(`${S}: lists changed lines`, !v.marks.changed.length || blk[3].includes(v.marks.changed.join(', ')));
  }
  const det = secs.find((m) => m[1] === lab.id && m[2] === 'detection');
  ok(`static ${lab.id}: detection block exists`, det);
  if (det) {
    const p = pres(det[3]);
    eq(`static ${lab.id}: replay output equals the capture`, p[0] && p[0].body, lab.detection.attack.out + lab.detection.benign.out);
    for (const k of ['attack', 'benign']) ok(`static ${lab.id}: ${k} counts shown`, det[3].includes(`${lab.detection[k].events} events, ${lab.detection[k].alerts} alert`));
  }
}
const summary = page.match(/<caption>Recorded results for each lab and version[\s\S]*?<\/table>/);
ok('static summary table exists with six rows', summary && (summary[0].match(/<tr><th scope="row"/g) || []).length === 6);
ok('page loads the bench module and its stylesheet', page.includes('<script type="module" src="/assets/js/bench-vulnlab.js"></script>') && page.includes('/assets/css/bench-vulnlab.css'));
ok('page has the static and live regions', page.includes('class="bench-static"') && page.includes('data-bench="vulnlab"') && page.includes('data-bench-mount'));
ok('caption gives tag, commit, versions and the command', [pv.tag, pv.commit, `Python ${pv.python}`, `pytest ${pv.pytest}`, `sinkline ${pv.sinkline}`, `tripline ${pv.tripline}`, `pySigma ${pv.pysigma}`, pv.commands.tests].every((x) => page.includes(x)));
ok('page says it is recorded, not live', page.includes('Recorded, not live'));
const text = page.replace(/<(script|style|pre)[\s\S]*?<\/\1>/g, ' ').replace(/<[^>]+>/g, ' ');
ok('no first-person wording and no tool-authorship wording in the page text', !/\b(I|my|me|we|our)\b/.test(text) && !/\b(AI|Claude|LLM|ChatGPT)\b/.test(text));

if (process.argv.includes('--fresh')) {
  const args = [join(root, 'scripts', 'capture_vulnlab_bench.py'), '--check'];
  if (process.env.VL_CLONE) args.push('--clone', process.env.VL_CLONE);
  if (process.env.VL_VENV) args.push('--venv', process.env.VL_VENV);
  const r = spawnSync(process.env.PYTHON || 'python', args, { encoding: 'utf8' });
  const last = (r.stdout || '').trim().split('\n').pop();
  eq('capture --check against a fresh run', r.status === 0 && last.endsWith('OK'), true);
  console.log(last || r.stderr);
}

if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nFAILED: ${failures.length} of ${checks} checks`);
  process.exit(1);
}
console.log(`bench-vulnlab consistency: ${checks} checks passed (3 labs, 6 versions, 9 static blocks, live bench and static fallback)`);
