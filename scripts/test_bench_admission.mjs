// Consistency test for the kevgate-admit "Admission desk". It runs nothing but Node and reads files; it does not run the webhook.
//
//   node scripts/test_bench_admission.mjs            offline checks
//   node scripts/test_bench_admission.mjs --fresh [--go PATH]   also run `python scripts/capture_admission_bench.py --check`
//                                                    (clones the tag, builds it with Go, runs it; needs git, Go, network)
//
// 1. The stored data is complete (5 images x 3 namespace scopes, 3 images x 3 report states) and internally consistent: the
//    decision, the rule names and the finding lines stored beside each raw response equal what the raw response text says.
// 2. For the four demo scenarios that the README prints (enforce: KEV, over-threshold, tag-only; audit: over-threshold), the
//    stored message or warning text appears verbatim in the README's transcript at the tag.
// 3. Everything the live desk would display (stamp, rule line, message, warnings, findings table, raw JSON, scanner table)
//    equals the stored response, for every combination. The module is mounted on a stub DOM and driven through its radios.
// 4. Everything the no-JS fallback in the built page displays equals the stored responses, in order.
// 5. The transcripts quoted on the page are in the README, and every function the lookup-path plate names was verified at the tag.
// That the stored data equals a fresh run of the real binary is checked by `python scripts/capture_admission_bench.py --check`.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(p, 'utf8').replace(/\r\n/g, '\n');
const data = JSON.parse(read(join(root, 'assets', 'data', 'admission-bench.json')));
const readme = JSON.parse(read(join(root, 'assets', 'data', 'admission-bench-readme.json')));
const { verdict, model, record, mount } = await import(pathToFileURL(join(root, 'assets', 'js', 'bench-kevgate-admit.js')).href);

let checks = 0;
const failures = [];
function eq(label, got, want) {
  checks += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) failures.push(`${label}\n  got:  ${JSON.stringify(got).slice(0, 200)}\n  want: ${JSON.stringify(want).slice(0, 200)}`);
}
function ok(label, cond) { eq(label, !!cond, true); }

const msgOf = (rec) => (rec.raw.response.status ? rec.raw.response.status.message : '');
const warnsOf = (rec) => rec.raw.response.warnings || [];
const all = [
  ...data.results.map((r) => ({ r, view: 'decision', a: r.image, b: r.policy })),
  ...data.signed.results.map((r) => ({ r, view: 'signed', a: r.image, b: r.state })),
];
const name = (x) => `${x.view} ${x.a}/${x.b}`;

// ---- 1. completeness and consistency
eq('5 images', data.images.map((i) => i.id), ['clean', 'kev', 'over', 'tag', 'evil']);
eq('3 policies', data.policies.map((p) => p.id), ['enforce', 'audit', 'default']);
eq('15 decision responses', data.results.length, 15);
eq('9 signed-evidence responses', data.signed.results.length, 9);
for (const i of data.images) for (const p of data.policies) eq(`one response for ${i.id}/${p.id}`, data.results.filter((r) => r.image === i.id && r.policy === p.id).length, 1);
for (const i of data.signed.images) for (const s of data.signed.states) eq(`one signed response for ${i}/${s.id}`, data.signed.results.filter((r) => r.image === i && r.state === s.id).length, 1);

for (const x of all) {
  const rec = x.r, resp = rec.raw.response;
  eq(`${name(x)}: AdmissionReview envelope`, [rec.raw.apiVersion, rec.raw.kind, resp.uid], ['admission.k8s.io/v1', 'AdmissionReview', 'u1']);
  eq(`${name(x)}: stored decision equals verdict(raw)`, rec.decision, verdict(rec.raw));
  eq(`${name(x)}: message exists exactly when denied`, !!msgOf(rec), !resp.allowed);
  if (!resp.allowed) eq(`${name(x)}: denial is 403 Forbidden`, [resp.status.code, resp.status.reason], [403, 'Forbidden']);
  const fromText = msgOf(rec) ? [...msgOf(rec).matchAll(/^- \[(\w+)\] /gm)].map((m) => m[1]) : warnsOf(rec).flatMap((w) => [...w.matchAll(/would deny \[(\w+)\]/g)].map((m) => m[1]));
  eq(`${name(x)}: stored rules equal the rules named in the text`, rec.rules, fromText);
  if (rec.decision === 'allowed') eq(`${name(x)}: allowed without warnings fires no rule`, rec.rules, []);
  for (const f of rec.findings) {
    const line = msgOf(rec).split('\n').find((l) => l.startsWith('    ' + f.cve));
    ok(`${name(x)}: finding line for ${f.cve} is in the message`, line);
    if (line) {
      ok(`${name(x)}: ${f.cve} risk ${f.risk} is on its line`, new RegExp('risk\\s+' + f.risk.toFixed(1).replace('.', '\\.') + '(\\s|$)').test(line));
      eq(`${name(x)}: ${f.cve} KEV flag equals the text`, f.kev, line.includes(' KEV '));
      ok(`${name(x)}: ${f.cve} package is on its line`, !f.pkg || line.endsWith(f.pkg));
    }
    ok(`${name(x)}: worked figure for ${f.cve} ends in the printed risk`, f.worked.endsWith('= ' + f.risk) && f.worked.startsWith('100 * ('));
  }
}
// the audit-mode and malformed-reference cases the page's caption describes
eq('audit mode admits what enforce denies (kev)', [record(data, 'decision', 'kev', 'enforce').decision, record(data, 'decision', 'kev', 'audit').decision], ['denied', 'warned']);
eq('malformed reference is an imageRef denial under enforce', record(data, 'decision', 'evil', 'enforce').rules, ['imageRef']);
ok('malformed reference text names the dot-segment reference', msgOf(record(data, 'decision', 'evil', 'enforce')).includes('ghcr.io/org/../evil'));
eq('over-threshold is allowed in the default scope (no maxRisk there)', record(data, 'decision', 'over', 'default').decision, 'allowed');
eq('valid signature: kev judged on content', record(data, 'signed', 'kev', 'valid').rules, ['denyKev', 'maxRisk']);
for (const s of ['tampered', 'missing']) for (const i of data.signed.images) {
  const rec = record(data, 'signed', i, s);
  eq(`signed ${i}/${s}: denied by requireEvidence and never scored`, [rec.decision, rec.rules, rec.findings.length], ['denied', ['requireEvidence'], 0]);
  ok(`signed ${i}/${s}: text says ${s === 'missing' ? 'unsigned' : 'signature is invalid'}`, msgOf(rec).includes(s === 'missing' ? 'scan report is unsigned' : 'scan report signature is invalid'));
}

// ---- 2. README transcript
const readmeText = readme.blocks.join('\n');
eq('README blocks are from the same tag and commit', [readme.tag, readme.commit], [data.provenance.tag, data.provenance.commit]);
const mustBeInReadme = [['enforce', 'kev'], ['enforce', 'over'], ['audit', 'over'], ['enforce', 'tag']];
for (const [p, i] of mustBeInReadme) {
  const rec = record(data, 'decision', i, p);
  const parts = msgOf(rec) ? [msgOf(rec)] : warnsOf(rec);
  ok(`${p}/${i}: has text to compare`, parts.length > 0);
  for (const part of parts) ok(`${p}/${i}: response text appears verbatim in the README transcript`, readmeText.includes(part));
}
let inReadme = 0;
for (const x of all) {
  const parts = msgOf(x.r) ? [msgOf(x.r)] : warnsOf(x.r);
  const want = parts.length ? parts.every((p) => readmeText.includes(p)) : null;
  eq(`${name(x)}: in_readme flag equals a fresh comparison`, x.r.in_readme, want);
  if (want) inReadme += 1;
}
ok('at least the four demo scenarios are flagged in_readme', inReadme >= 4);

// ---- 3. the live desk on a stub DOM
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.children = []; this.text = ''; this.handlers = {}; this.checked = false; this.hidden = false; this.className = ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'class') this.className = String(v); }
  getAttribute(k) { return this.attrs[k]; }
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
const pick = (n, value) => { const r = radios.find((x) => x.attrs.name === n && x.attrs.value === value); r.checked = true; r.fire('change'); };
eq('live desk has 3 + 5 + 3 + 3 + 3 radio buttons', radios.length, 17);
ok('every radio sits in a label inside a fieldset with a legend', rootEl.find((e) => e.tag === 'fieldset').length === 5 && rootEl.find((e) => e.tag === 'legend').length === 5);
const out = () => rootEl.find(cls('ad-out'))[0];
const live = () => rootEl.find((e) => e.attrs.role === 'status')[0];
const pres = () => out().find((e) => e.tag === 'pre');
const rowsOf = (tbl) => tbl.find((e) => e.tag === 'tbody')[0].children.map((tr) => tr.children.map((c) => c.textContent));
const stampText = () => out().find((e) => e.className.startsWith('stamp'))[0];

for (const x of all) {
  if (x.view === 'decision') { pick('ad-view', 'decision'); pick('ad-img', x.a); pick('ad-pol', x.b); }
  else { pick('ad-view', 'signed'); pick('ad-simg', x.a); pick('ad-st', x.b); }
  const rec = x.r, L = 'live ' + name(x);
  const m = model(data, x.view, x.a, x.b);
  const stamp = stampText();
  eq(`${L}: stamp text`, stamp.textContent, { allowed: 'Allowed', denied: 'Denied', warned: 'Allowed with warning' }[rec.decision]);
  eq(`${L}: stamp class`, stamp.className, 'stamp ' + { allowed: 'pass', denied: 'fail', warned: 'limit' }[rec.decision]);
  const p = pres();
  const msgPre = p.filter((e) => (e.attrs['data-label'] || '').startsWith('status.message'));
  const warnPre = p.filter((e) => (e.attrs['data-label'] || '').startsWith('warnings'));
  eq(`${L}: denial text is the stored message`, msgPre.length ? msgPre[0].textContent : '', msgOf(rec));
  eq(`${L}: warnings are the stored warnings`, warnPre.length ? warnPre[0].textContent : '', warnsOf(rec).join('\n'));
  const rawPre = p.filter((e) => (e.attrs['data-label'] || '').startsWith('JSON as returned'))[0];
  eq(`${L}: raw JSON equals the stored response`, JSON.parse(rawPre.textContent), rec.raw);
  const tables = out().find((e) => e.tag === 'table');
  eq(`${L}: findings table rows`, tables.length ? rowsOf(tables[0]) : [], rec.findings.map((f) => [f.rule, f.cve, f.kev ? 'KEV' : 'no', f.risk.toFixed(1), f.pkg]));
  ok(`${L}: rule line names the stored rules`, rec.rules.every((r) => out().textContent.includes(r)));
  ok(`${L}: request line names the image reference`, out().textContent.includes(data.images.find((i) => i.id === x.a).ref));
  eq(`${L}: live region`, live().textContent, m.spoken);
}
pick('ad-view', 'scanner');
{
  const tables = out().find((e) => e.tag === 'table');
  const s = data.scanner.parser;
  eq('live scanner: one table', tables.length, 1);
  eq('live scanner: rows are the parsed findings', rowsOf(tables[0]).map((r) => r.slice(0, 5)), s.findings.map((f) => [f.ID, f.Package, f.Installed, f.Fixed || 'no fix', f.Severity]));
  eq('live scanner: risk column', rowsOf(tables[0]).map((r) => r[7]), s.findings.map((f) => f.Risk.toFixed(1)));
  eq('live scanner: raw entry count and findings', [data.scanner.raw_entries, s.findings.length, new Set(s.findings.map((f) => f.ID)).size], [10, 10, 10]);
}

// ---- 4. the no-JS fallback in the built page
const page = read(join(root, 'projects', 'kevgate-admit', 'index.html'));
const unesc = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const stat = page.slice(page.indexOf('class="bench-static"'), page.indexOf('data-bench-mount'));
const msgs = [...stat.matchAll(/<code class="ad-msg">([\s\S]*?)<\/code>/g)].map((m) => unesc(m[1]));
const expected = all.map((x) => {
  const parts = [];
  if (msgOf(x.r)) parts.push(msgOf(x.r));
  parts.push(...warnsOf(x.r));
  return parts.length ? parts.join('\n') : '(no message, no warnings)';
});
eq('static: 24 recorded responses', msgs.length, 24);
eq('static: every response text equals the stored capture, in order', msgs, expected);
const stamps = [...stat.matchAll(/<span class="stamp[^"]*">([^<]*)<\/span>/g)].map((m) => m[1]);
eq('static: stamps carry text for every response', stamps, all.map((x) => ({ allowed: 'Allowed', denied: 'Denied', warned: 'Allowed with warning' }[x.r.decision])));
for (const f of data.scanner.parser.findings) ok(`static: scanner row ${f.ID}`, stat.includes(`<th scope="row">${f.ID}</th>`));
ok('static: the formula is shown', stat.includes(data.provenance.formula));
ok('page loads the bench module and stylesheet', page.includes('<script type="module" src="/assets/js/bench-kevgate-admit.js"></script>') && page.includes('/assets/css/bench-kevgate-admit.css'));
ok('page has the static and live regions', page.includes('data-bench="kevgate-admit"') && page.includes('class="bench-static"') && page.includes('data-bench-mount'));
const pv = data.provenance;
ok('caption gives the command, tag, commit, Go version and date', [pv.command, pv.tag, pv.commit.slice(0, 7), pv.go, pv.captured, 'capture_admission_bench.py'].every((s) => page.includes(s)));
ok('caption says it is recorded and the page evaluates no policy', page.includes('Recorded, not live') && page.includes('The page evaluates no policy'));
ok('page states the capture counts', page.includes('24 recorded responses (15 decisions, 9 with signed evidence)'));

// ---- 5. quoted transcripts and the names on the lookup-path plate
for (const label of ['End-to-end transcript (README)', 'Outage transcript (README)']) {
  const m = page.match(new RegExp('<pre data-copy data-label="' + label.replace(/[()]/g, '\\$&') + '"[^>]*><code>([\\s\\S]*?)</code></pre>'));
  ok(`page has the "${label}" block`, m);
  if (!m) continue;
  let bad = 0, n = 0;
  for (const line of unesc(m[1]).split('\n')) {
    for (const seg of line.split('...').map((s) => s.trim()).filter(Boolean)) { n += 1; if (!readmeText.includes(seg)) { bad += 1; failures.push(`"${label}": not in the README: ${seg.slice(0, 120)}`); } }
  }
  ok(`"${label}" has lines to compare`, n > 5);
}
const verified = new Set(pv.names_verified.map((s) => s.split(': ')[1]));
const plate = page.slice(page.indexOf('class="plate admit-path"'));
const plateNames = [...plate.slice(0, plate.indexOf('</ol>')).matchAll(/<code>([^<]+)<\/code>/g)].map((m) => m[1]);
ok('lookup-path plate names functions', plateNames.length >= 15);
for (const n of plateNames) ok(`lookup-path name ${n} was found at the tag`, verified.has(n.split('.').pop()));

// ---- optional: a fresh run of the real binary
if (process.argv.includes('--fresh')) {
  const gi = process.argv.indexOf('--go');
  const r = spawnSync('python', [join(root, 'scripts', 'capture_admission_bench.py'), '--check', ...(gi > 0 ? ['--go', process.argv[gi + 1]] : [])], { encoding: 'utf8' });
  console.log((r.stdout + r.stderr).trim().split('\n').slice(-2).join('\n'));
  ok('capture_admission_bench.py --check passes (stored data equals a fresh run)', r.status === 0);
}

if (failures.length) {
  console.error(failures.join('\n'));
  console.error(`\nFAILED: ${failures.length} of ${checks} checks`);
  process.exit(1);
}
console.log(`bench-kevgate-admit: ${checks} checks passed (${all.length} responses, live desk on a stub DOM, no-JS fallback, README transcript)`);
