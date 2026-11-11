/* Rule bench for the tripline sheet. Re-implements the conditions of two Sigma rules (the stock SigmaHQ
   "Setuid and Setgid" rule and tripline's replacement) so a visitor can try a chmod command line.
   The rule patterns are read from /assets/data/bench-tripline.json, which scripts/gen_bench_tripline.py
   copies from the rule YAML. tripline's own compiler is the source of truth: scripts/test_bench_tripline.mjs
   checks this file against its verdicts. The page is complete without this script. */

// Python's \s and \w differ from JavaScript's; translate them so both engines accept the same text.
const SP = '\\t-\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const WD = '\\p{L}\\p{N}_';

export function py2js(src) {
  let out = '', cls = false;
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === '\\') {
      const n = src[++i];
      out += n === 's' ? (cls ? SP : '[' + SP + ']') : n === 'S' ? '[^' + SP + ']'
        : n === 'w' ? (cls ? WD : '[' + WD + ']') : '\\' + n;
    } else if (c === '[' && !cls) { cls = true; out += c; }
    else if (c === ']' && cls) { cls = false; out += c; }
    else out += c === '$' && !cls ? '(?=\\n?$)' : c; // Python $ also matches before a final newline
  }
  return new RegExp(out, 'u');
}

const lit = (s) => new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'iu'); // Sigma contains: case-insensitive

export function compile(d) {
  return {
    root: d.stock.root.map(lit), perm: d.stock.perm.map(lit),
    image: new RegExp(d.custom.image.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$', 'iu'),
    sym: py2js(d.custom.symbolic), oct: py2js(d.custom.octal), filt: py2js(d.custom.filter),
  };
}

// Returns the selection results and verdicts: s = [root, perm, verdict], r = [image, symbolic, octal, filter, verdict].
export function decide(k, image, cmd) {
  const root = k.root.some((x) => x.test(cmd)), perm = k.perm.some((x) => x.test(cmd));
  const im = k.image.test(image), sy = k.sym.test(cmd), oc = k.oct.test(cmd), fi = k.filt.test(cmd);
  const n = (b) => +b;
  return { s: [n(root), n(perm), n(root && perm)], r: [n(im), n(sy), n(oc), n(fi), n(im && (sy || oc) && !fi)] };
}

export function reasons(res) {
  const [root, perm, sv] = res.s, [im, sy, oc, fi, rv] = res.r;
  const stock = sv ? "Has both 'chown root' and the literal ' chmod u+s' or ' chmod g+s'."
    : !root && !perm ? "Has neither 'chown root' nor the literal ' chmod u+s' or ' chmod g+s'."
    : !root ? "Has the chmod text but no 'chown root'; the rule needs both."
    : "Has 'chown root' but not the literal ' chmod u+s' or ' chmod g+s'; the rule needs both.";
  const form = sy && oc ? 'symbolic and octal' : sy ? 'symbolic' : 'octal';
  const custom = rv ? 'Image ends with /chmod and the mode sets setuid or setgid (' + form + ' form).'
    : !im ? ((sy || oc) ? 'The mode would match, but Image does not end with /chmod, so this event is not the chmod itself.'
      : 'Image does not end with /chmod and no setuid or setgid mode is present.')
    : !(sy || oc) ? 'No setuid or setgid mode: no symbolic s bit and no octal mode 2xxx to 7xxx.'
    : 'Excluded: every file operand is under /usr/share/doc/.';
  return { stock, custom };
}

/* ---------------------------------------------------------------- page ---------------------------------------- */
const STOCK_CONDS = [
  ['selection_root', "CommandLine contains 'chown root'"],
  ['selection_perm', "CommandLine contains ' chmod u+s' or ' chmod g+s'"],
];
const CUSTOM_CONDS = [
  ['selection_image', 'Image ends with /chmod'],
  ['selection_symbolic', 'symbolic mode with the s bit (u+s, ug+s, u+xs, a+s, g+w,u+s)'],
  ['selection_octal', 'octal mode 2xxx to 7xxx, optional leading zero'],
  ['filter_tmp_runner', 'every file operand is under /usr/share/doc/'],
];
const IMAGES = ['/usr/bin/chmod', '/bin/chmod', '/usr/bin/sudo', '/usr/bin/dash'];
const REPO = 'https://github.com/samiali38183/tripline/blob/main/';

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); }
  for (const c of kids) if (c) e.append(c);
  return e;
}
const stamp = (on) => h('span', { class: 'stamp' + (on ? '' : ' off'), text: on ? 'Flagged' : 'Not flagged' });

function panel(title, ruleId, href, conds, vals, cond, verdict, reason, id) {
  const ul = h('ul', { class: 'bl-conds' });
  conds.forEach(([name, text], i) => {
    const on = vals[i];
    ul.append(h('li', { 'data-on': on }, h('span', { class: 'bx', 'aria-hidden': 'true' }),
      h('span', null, h('code', { text: name }), h('span', { class: 'w', text: on ? ' met: ' : ' not met: ' }), document.createTextNode(text))));
  });
  return h('section', { class: 'bl-p', 'aria-labelledby': id },
    h('h3', { id, class: 'bl-t' }, document.createTextNode(title + ' '), h('a', { href, text: ruleId })),
    ul, h('p', { class: 'bl-c' }, h('span', { class: 'label', text: 'condition ' }), h('code', { text: cond })),
    h('p', { class: 'bl-v' }, stamp(verdict)), h('p', { class: 'bl-r', text: reason }));
}

async function init() {
  const root = document.querySelector('[data-bench="tripline"]');
  if (!root) return;
  const live = root.querySelector('.bench-live'), stat = root.querySelector('.bench-static');
  const res = await fetch('/assets/data/bench-tripline.json');
  if (!res.ok) return;
  const d = await res.json();
  const k = compile(d), ev = d.events, m = d.meta;

  const img = h('select', { id: 'bl-img' });
  IMAGES.forEach((v) => img.append(h('option', { value: v, text: v })));
  const cmd = h('input', { id: 'bl-cmd', type: 'text', spellcheck: 'false', autocomplete: 'off', autocapitalize: 'off', maxlength: '300' });
  const out = h('div', { class: 'bl-out' });
  const status = h('p', { class: 'sr', role: 'status', 'aria-live': 'polite' });
  let timer;

  function run(announce) {
    const r = decide(k, img.value, cmd.value), why = reasons(r);
    out.replaceChildren(
      panel('Stock SigmaHQ rule', m.stock.id.slice(0, 8), REPO + m.stock.file, STOCK_CONDS, r.s, 'all of selection_*', r.s[2], why.stock, 'bl-h1'),
      panel("tripline's replacement rule", 'tripline_lnx_chmod_setuid_setgid_any_form', REPO + m.custom.file, CUSTOM_CONDS, r.r,
        'selection_image and (selection_symbolic or selection_octal) and not filter_tmp_runner', r.r[4], why.custom, 'bl-h2'));
    const say = 'Stock rule: ' + (r.s[2] ? 'flagged' : 'not flagged') + '. Replacement rule: ' + (r.r[4] ? 'flagged' : 'not flagged') + '.';
    clearTimeout(timer);
    if (announce) status.textContent = say; else timer = setTimeout(() => { status.textContent = say; }, 500);
  }
  function load(i, c) {
    if (![...img.options].some((o) => o.value === i)) img.append(h('option', { value: i, text: i }));
    img.value = i; cmd.value = c; run(true);
  }

  const presets = h('div', { class: 'bl-presets', role: 'group', 'aria-label': 'Example command lines' });
  d.presets.forEach((p) => {
    const b = h('button', { type: 'button', class: 'bl-b', text: p.l });
    b.addEventListener('click', () => load(p.i, p.c));
    presets.append(b);
  });

  // Replay view: the 36 recorded events and what each rule decided on them.
  const sel = h('select', { id: 'bl-ev' });
  ev.forEach((e, i) => sel.append(h('option', { value: i, text: (i + 1) + ': ' + (e.c.length > 54 ? e.c.slice(0, 54) + '…' : e.c) })));
  const detail = h('div', { class: 'bl-ev', 'aria-live': 'polite' });
  const rows = [['As found', 'stock rule', 's'], ['As left', 'replacement rule', 'r']].map(([a, b, key]) => {
    const strip = h('div', { class: 'strip', 'aria-hidden': 'true' });
    ev.forEach((e, i) => {
      const exp = d.expected.includes(i), hit = e[key];
      const t = h('i', { 'data-s': hit ? (exp ? 'hit' : 'fp') : (exp ? 'miss' : 'neg') });
      if ((i + 1) % 10 === 0) { t.className = 'm'; t.dataset.n = i + 1; }
      t.addEventListener('click', () => pick(i));
      strip.append(t);
    });
    const n = ev.filter((e) => e[key]).length;
    return { strip, row: h('div', { class: 'srow' }, h('span', { class: 'label', text: a }), strip,
      h('p', { class: 'val' }, h('b', { text: String(n) }), document.createTextNode(' of ' + ev.length + ' flagged by the ' + b))) };
  });
  function pick(i, scroll) {
    sel.value = i;
    const e = ev[i], exp = d.expected.includes(i);
    rows.forEach((r, j) => r.strip.querySelectorAll('i').forEach((t, x) => t.classList.toggle('sel', x === i)));
    const tryit = h('button', { type: 'button', class: 'bl-b', text: 'Try this in the bench' });
    tryit.disabled = e.c.endsWith('…');
    tryit.addEventListener('click', () => { load(e.i, e.c); cmd.focus(); });
    detail.replaceChildren(
      h('p', { class: 'bl-e' }, h('span', { class: 'label', text: 'Event ' + (i + 1) + ' of ' + ev.length }), document.createTextNode(' '),
        exp ? h('span', { class: 'label', text: '(a chmod execution the scenario expects to be flagged)' }) : null),
      h('p', { class: 'bl-im' }, h('span', { class: 'label', text: 'Image ' }), h('code', { text: e.i })),
      h('p', { class: 'bl-im' }, h('span', { class: 'label', text: 'Command line ' }), h('code', { text: e.c })),
      h('p', { class: 'bl-v2' }, h('span', { class: 'label', text: 'Stock ' }), stamp(e.s), document.createTextNode(' '),
        h('span', { class: 'label', text: 'Replacement ' }), stamp(e.r)), tryit);
    if (scroll) root.scrollIntoView({ block: 'nearest' });
  }
  sel.addEventListener('change', () => pick(+sel.value));
  const step = (dx) => { pick((+sel.value + dx + ev.length) % ev.length); };
  const prev = h('button', { type: 'button', class: 'bl-b', text: 'Previous event' });
  const next = h('button', { type: 'button', class: 'bl-b', text: 'Next event' });
  prev.addEventListener('click', () => step(-1));
  next.addEventListener('click', () => step(1));

  // The strips at the top of the page are the same 36 events: clicking a tick opens it here.
  document.querySelectorAll('.reading-band .strips .strip').forEach((s) => s.querySelectorAll('i').forEach((t, i) => {
    t.style.cursor = 'pointer'; t.title = 'Event ' + (i + 1) + ': ' + ev[i].c.slice(0, 60);
    t.addEventListener('click', () => pick(i, true));
  }));

  const field = (label, ctl) => h('div', { class: 'bl-f' }, h('label', { for: ctl.id, text: label }), ctl);
  live.replaceChildren(
    h('h2', { class: 'sr', text: 'Rule bench' }),
    h('p', { class: 'bl-note' }, h('span', { class: 'label', text: 'Computed in your browser' }),
      document.createTextNode(' from the two rules’ conditions; nothing is sent anywhere.')),
    h('form', { class: 'bl-in' }, field('Image', img), field('Command line', cmd)),
    h('p', { class: 'label', text: 'Examples' }), presets, out, status,
    h('h3', { class: 'bl-rt', text: 'Replay of the 36 recorded events' }),
    h('p', { class: 'bl-rn', text: 'Telemetry recorded from Atomic Red Team T1548.001 on a GitHub-hosted runner, run ' + m.run + '. Click a tick, or choose an event.' }),
    h('div', { class: 'strips' }, rows[0].row, rows[1].row),
    h('div', { class: 'bl-pick' }, field('Recorded event', sel), prev, next), detail,
    h('p', { class: 'bl-prov label', text: 'tripline ' + m.tripline + ' at ' + m.commit + ' · rules read from the repository YAML · ' + m.parity_cases + ' parity cases checked against tripline’s compiler' }));
  load(d.presets[1].i, d.presets[1].c);
  pick(d.expected[0]);
  stat.hidden = true;
  live.hidden = false;
}

if (typeof document !== 'undefined') init().catch(() => { /* leave the recorded static state visible */ });
