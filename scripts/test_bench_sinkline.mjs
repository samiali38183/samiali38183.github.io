// Parity test for the sinkline "Sanitizer switch". Runs nothing but Node and reads files; it does not run sinkline.
//
//   node scripts/test_bench_sinkline.mjs
//
// 1. The stored data (assets/data/bench-sinkline.json) equals the committed captures: every source equals its .py file and
//    every output equals its .txt file, and no file in assets/data/sinkline-bench is unlisted.
// 2. Everything the live bench would display (code pane and output pane, for every example and variant) equals the
//    stored capture. The module is mounted on a small stub DOM and driven through its radio buttons.
// 3. Everything the no-JS fallback in the built page displays equals the stored capture.
// 4. The recorded findings agree with the recorded text (a finding exists exactly when the text has one) and the wrong-class
//    variants keep their finding with a sanitizer step for a different CWE.
// That every capture equals a fresh run of the real CLI is checked by `python scripts/capture_sinkline_bench.py --check`.
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'assets', 'data', 'sinkline-bench');
const read = (p) => readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
const data = JSON.parse(read(join(root, 'assets', 'data', 'bench-sinkline.json')));
const { model, mount } = await import(pathToFileURL(join(root, 'assets', 'js', 'bench-sinkline.js')).href);

let checks = 0;
const failures = [];
function eq(label, got, want) {
  checks += 1;
  if (got !== want) failures.push(`${label}\n  got:  ${JSON.stringify(got).slice(0, 160)}\n  want: ${JSON.stringify(want).slice(0, 160)}`);
}
function ok(label, cond) { eq(label, !!cond, true); }

// ---- 1. data equals committed files
const all = data.examples.flatMap((e) => e.variants.map((v) => ({ ex: e, v }))).concat(data.extra.map((v) => ({ ex: null, v })));
const listed = new Set();
for (const { v } of all) {
  eq(`${v.file} source equals file`, v.code, read(join(dir, v.file)));
  const txt = v.file.replace(/\.py$/, '.txt');
  eq(`${txt} equals stored output`, v.out, read(join(dir, txt)));
  listed.add(v.file); listed.add(txt);
  ok(`${v.file} no run errors`, v.errors.length === 0);
}
eq('no unlisted files', readdirSync(dir).filter((f) => !listed.has(f)).join(','), '');
eq('provenance tool', data.provenance.tool + ' ' + data.provenance.version, 'sinkline 0.5.1');

// ---- 4. findings agree with the text; wrong-class variants
for (const { ex, v } of all) {
  const textFound = /^\[(CRITICAL|HIGH|MEDIUM|LOW)\] SL-/m.test(v.out);
  eq(`${v.file} finding in data matches text`, v.findings.length > 0, textFound);
  eq(`${v.file} exit status matches (1 with finding, else 0)`, v.status, textFound ? 1 : 0);
  if (v.findings[0]) {
    const f = v.findings[0];
    ok(`${v.file} text names ${f.rule_id} and ${f.cwe}`, v.out.includes(f.rule_id) && v.out.includes(f.cwe));
    ok(`${v.file} text has the fix line`, v.out.includes('fix: ' + f.fix));
  }
  if (ex && v.id === 'right') eq(`${v.file} right-class variant has no finding`, v.findings.length, 0);
  if (ex && v.id === 'wrong') {
    const f = v.findings[0];
    ok(`${v.file} wrong-class variant keeps its finding`, f && f.cwe === ex.cwe);
    const san = f && f.route.find((s) => s.kind === 'sanitizer');
    ok(`${v.file} route has a sanitizer step for another CWE`, san && /clears CWE-\d+/.test(san.note) && !san.note.includes(ex.cwe));
  }
  if (ex && v.id === 'unsafe') eq(`${v.file} unsafe variant has a finding for ${ex.cwe}`, v.findings[0] && v.findings[0].cwe, ex.cwe);
}

// ---- 2. the live bench on a stub DOM
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
const doc = {
  createElement: (t) => new El(t),
  createTextNode: (s) => { const e = new El('#text'); e.text = s; return e; },
};
const rootEl = new El('div');
mount(doc, rootEl, data);
const cls = (c) => (e) => e.className.split(' ').includes(c);
const codePre = rootEl.find(cls('sw-code'))[0];
const outPre = rootEl.find(cls('sw-out'))[0];
const verdict = rootEl.find(cls('stamp'))[0];
const radios = rootEl.find((e) => e.tag === 'input');
const pick = (name, value) => { const r = radios.find((x) => x.attrs.name === name && x.attrs.value === value); r.checked = true; r.fire('change'); };
eq('live bench has 3 + 3 radio buttons', radios.length, 6);

for (const ex of data.examples) {
  for (const v of ex.variants) {
    pick('sw-ex', ex.id); pick('sw-var', v.id);
    const shownOut = outPre.find((e) => e.tag === 'code')[0].textContent;
    const shownCode = codePre.find(cls('c')).map((e) => e.textContent).join('\n') + '\n';
    const label = `live ${ex.id}/${v.id}`;
    eq(`${label}: output pane equals ${v.file.replace(/\.py$/, '.txt')}`, shownOut, read(join(dir, v.file.replace(/\.py$/, '.txt'))));
    eq(`${label}: code pane equals ${v.file}`, shownCode, read(join(dir, v.file)));
    eq(`${label}: output pre label`, outPre.attrs['data-label'], '$ ' + data.provenance.command.replace('FILE', v.file));
    eq(`${label}: verdict text`, verdict.textContent, v.findings.length ? 'Finding' : 'No finding');
    eq(`${label}: verdict class`, verdict.className, 'stamp ' + (v.findings.length ? 'fail' : 'pass'));
    eq(`${label}: changed lines marked`, codePre.find(cls('d')).map((e, i) => (e.textContent ? i + 1 : 0)).filter(Boolean).join(','), v.changed.join(','));
    const m = model(data, ex.id, v.id);
    eq(`${label}: model output is the stored capture`, m.out, v.out);
  }
}

// ---- 3. the no-JS fallback in the built page
const page = read(join(root, 'projects', 'sinkline', 'index.html'));
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const pres = [...page.matchAll(/<pre data-label="([^"]*)" tabindex="0"><code>([\s\S]*?)<\/code><\/pre>/g)]
  .map((m) => ({ label: unesc(m[1]), body: unesc(m[2]) }));
for (const { v } of data.examples.flatMap((e) => e.variants.map((x) => ({ v: x })))) {
  const src = pres.filter((p) => p.label === v.file);
  const out = pres.filter((p) => p.label === '$ ' + data.provenance.command.replace('FILE', v.file));
  eq(`static ${v.file}: one source block`, src.length, 1);
  eq(`static ${v.file}: one output block`, out.length, 1);
  if (src[0]) eq(`static ${v.file}: source equals capture`, src[0].body, v.code);
  if (out[0]) eq(`static ${v.file}: output equals capture`, out[0].body, v.out);
}
ok('page loads the bench module', page.includes('<script type="module" src="/assets/js/bench-sinkline.js"></script>'));
ok('page has the static and live regions', page.includes('class="bench-static"') && page.includes('data-bench-mount'));
ok('page caption gives command and version', page.includes(data.provenance.command) && page.includes('sinkline ' + data.provenance.version) && page.includes(data.provenance.commit));
// the limits note quotes the extra capture; it must match too
const extra = data.extra[0];
eq('extra capture equals file', extra.out, read(join(dir, 'html-wrong-direct.txt')));
ok('limits note names the extra capture', page.includes('html-wrong-direct.txt'));

if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nFAILED: ${failures.length} of ${checks} checks`);
  process.exit(1);
}
console.log(`bench-sinkline parity: ${checks} checks passed (${data.examples.length} examples, ${all.length} captures, live bench and static fallback)`);
