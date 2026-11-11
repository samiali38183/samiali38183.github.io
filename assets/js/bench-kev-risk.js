/* Weight bench for the kev-risk-prioritization sheet. Re-implements the documented score of kev_prioritize.py
   (v0.2.0) on its 20 synthetic sample findings so a visitor can move the four weights and watch the order change:
     risk = round(100 * (w_kev*kev + w_acr*acr/8 + w_epss*epss + w_cvss*cvss/10) / sum(weights), 1)
   sorted by risk, then EPSS, then CVSS (descending; ties keep input order). The tool itself is the source of truth:
   scripts/test_bench_kev.mjs checks this file against its output (assets/data/kev-bench-parity.json).
   The page is complete without this script. Findings are read from /assets/data/bench-kev-risk.json. */

const clamp = (x, lo, hi) => Math.min(Math.max(x, lo), hi);

// w = [kev, acr, epss, cvss]. Same operations in the same order as kev_prioritize.risk_score, so the floats match.
export function riskScore(kev, acr, epss, cvss, w) {
  acr = clamp(acr, 0, 8); epss = clamp(epss, 0, 1); cvss = clamp(cvss, 0, 10);
  let s = w[0] * (kev ? 1 : 0) + w[1] * (acr / 8) + w[2] * epss;
  let t = w[0] + w[1] + w[2];
  s += w[3] * (cvss / 10); t += w[3];
  return round1(100 * s / t);
}

// Python's round(x, 1): correct rounding of the exact binary value, and half to even on exact ties. toFixed does the
// first; the only exact ties at one decimal are x.25 and x.75, where it rounds up instead, so those are handled here.
export function round1(x) {
  if (Number.isInteger(x * 4) && !Number.isInteger(x * 2)) { const k = Math.floor(x * 10); return (k % 2 ? k + 1 : k) / 10; }
  return Number(x.toFixed(1));
}

// f = [cve, asset, acr, cvss, epss, days_open, kev]. Returns indices into f and scores, best first (score is null when
// every weight is 0: the tool would divide by zero).
export function rank(f, w) {
  const zero = w[0] + w[1] + w[2] + w[3] === 0;
  const sc = f.map((r) => (zero ? null : riskScore(r[6], r[2], r[4], r[3], w)));
  const o = f.map((_, i) => i).sort((a, b) =>
    (zero ? 0 : sc[b] - sc[a]) || f[b][4] - f[a][4] || f[b][3] - f[a][3]);
  return { o, s: o.map((i) => sc[i]) };
}

export const kevInTop = (f, o, n) => o.slice(0, n).filter((i) => f[i][6]).length;

// Rows to display for weights w, with the move against the default order.
export function view(d, w) {
  const dflt = rank(d.findings, d.presets[0].w).o, cur = rank(d.findings, w);
  return cur.o.map((i, p) => {
    const r = d.findings[i];
    return { rank: p + 1, cve: r[0], asset: r[1], acr: r[2], cvss: r[3], epss: r[4], days: r[5], kev: r[6], score: cur.s[p], moved: dflt.indexOf(i) - p };
  });
}

/* ---------------------------------------------------------------- page ---------------------------------------- */
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); }
  for (const c of kids) if (c) e.append(c);
  return e;
}
const NAMES = [['kev', 'KEV match'], ['acr', 'Asset criticality (ACR)'], ['epss', 'EPSS'], ['cvss', 'CVSS']];
const two = (x) => Number(x).toFixed(2);

function strip(label, flags, unit) {
  const k = flags.filter(Boolean).length;
  const s = h('div', { class: 'strip', role: 'img', 'aria-label': label + ', ' + flags.length + ' top slots: ' + k + ' KEV finding' + (k === 1 ? '' : 's') + ', ' + (flags.length - k) + ' non-KEV' });
  flags.forEach((x) => s.append(h('i', { 'data-s': x ? 'hit' : 'miss' })));
  return h('div', { class: 'srow' }, h('span', { class: 'label', 'aria-hidden': 'true', text: label }), s,
    h('p', { class: 'val' }, h('b', { text: String(k) }), document.createTextNode(' of ' + flags.length + ' ' + unit)));
}

async function init() {
  const root = document.querySelector('[data-bench="kev-risk"]');
  if (!root) return;
  const live = root.querySelector('.bench-live'), stat = root.querySelector('.bench-static');
  const res = await fetch('/assets/data/bench-kev-risk.json');
  if (!res.ok) return;
  const d = await res.json(), F = d.findings, TOP = d.top, m = d.meta;
  const cvssOnly = d.presets.find((p) => p.k === 'cvss').w;
  const refKev = kevInTop(F, rank(F, cvssOnly).o, TOP);
  let timer;

  const status = h('p', { class: 'vh', role: 'status' });
  const sliders = NAMES.map(([k, label], i) => {
    const inp = h('input', { type: 'range', id: 'wb-' + k, min: '0', max: '1', step: '0.05', value: String(d.presets[0].w[i]) });
    const out = h('output', { for: 'wb-' + k, class: 'wb-o' });
    return { inp, out, box: h('div', { class: 'wb-s' }, h('label', { for: 'wb-' + k, text: label }), inp, out) };
  });
  const formula = h('code', { class: 'wb-f' });
  const counter = h('div', { class: 'strips wb-strips' });
  const zeroNote = h('p', { class: 'wb-z', hidden: '' }, document.createTextNode('All four weights are 0. The tool divides by the sum of the weights and would stop with an error, so there is no ranking to show.'));
  const tbody = h('tbody');
  const rows = F.map(() => h('tr'));
  const weights = () => sliders.map((s) => Number(s.inp.value));

  function render(immediate) {
    const w = weights(), v = view(d, w), zero = v[0].score === null;
    sliders.forEach((s, i) => { s.out.textContent = two(w[i]); });
    formula.textContent = '100 × (' + two(w[0]) + '·kev + ' + two(w[1]) + '·acr/8 + ' + two(w[2]) + '·epss + ' + two(w[3]) + '·cvss/10) ÷ ' + two(w[0] + w[1] + w[2] + w[3]);
    presetBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(d.presets[i].w.every((x, j) => x === w[j]))));
    zeroNote.hidden = !zero;
    const n = zero ? null : v.slice(0, TOP).filter((r) => r.kev).length;
    counter.replaceChildren(zero ? h('p', { class: 'val', text: 'No ranking' }) : strip('These weights', v.slice(0, TOP).map((r) => r.kev), 'KEV findings in the top ' + TOP),
      strip('CVSS only', rank(F, cvssOnly).o.slice(0, TOP).map((i) => F[i][6]), 'KEV findings in the top ' + TOP));
    tbody.replaceChildren(...v.map((r, p) => {
      const tr = rows[p];
      tr.className = p === TOP ? 'cut' : '';
      const mv = zero ? '' : r.moved > 0 ? 'up ' + r.moved : r.moved < 0 ? 'down ' + -r.moved : 'same';
      tr.replaceChildren(
        h('th', { scope: 'row', class: 'num', text: String(r.rank) }), h('td', { text: r.cve }), h('td', { text: r.asset }),
        h('td', { 'data-k': String(r.kev) }, h('span', { class: 'wb-sq', 'aria-hidden': 'true' }), document.createTextNode(r.kev ? 'KEV' : 'no')),
        h('td', { class: 'num', text: r.cvss.toFixed(1) }), h('td', { class: 'num', text: r.epss.toFixed(3) }),
        h('td', { class: 'num', text: String(r.acr) }), h('td', { class: 'num', text: String(r.days) }),
        h('td', { class: 'num wb-sc' }, h('span', { class: 'wb-bar', 'aria-hidden': 'true', style: 'width:' + (zero ? 0 : r.score) + '%' }), document.createTextNode(zero ? 'n/a' : r.score.toFixed(1))),
        h('td', { class: 'wb-mv', text: mv }));
      return tr;
    }));
    const say = zero ? 'All weights are 0: no ranking.' : 'Top three: ' + v.slice(0, 3).map((r) => r.cve + ' ' + r.score.toFixed(1)).join(', ') + '. KEV findings in the top ' + TOP + ': ' + n + ' of ' + TOP + '; CVSS-only sort: ' + refKev + ' of ' + TOP + '.';
    clearTimeout(timer);
    if (immediate) status.textContent = say; else timer = setTimeout(() => { status.textContent = say; }, 400);
  }

  const presetBtns = d.presets.map((p) => {
    const b = h('button', { type: 'button', class: 'bl-b', 'aria-pressed': 'false', text: p.l });
    b.addEventListener('click', () => { sliders.forEach((s, i) => { s.inp.value = String(p.w[i]); }); render(true); });
    return b;
  });
  live.addEventListener('submit', (e) => e.preventDefault());
  sliders.forEach((s) => s.inp.addEventListener('input', () => render(false)));

  const head = ['Rank', 'CVE', 'Asset', 'KEV', 'CVSS', 'EPSS', 'ACR', 'Days open', 'Risk score', 'Against default'];
  const table = h('table', { class: 'wb-t' },
    h('caption', { text: 'The 20 synthetic findings in the order the chosen weights give. A line marks the end of the top ' + TOP + '.' }),
    h('thead', null, h('tr', null, ...head.map((t, i) => h('th', { scope: 'col', class: i > 3 && i < 9 ? 'num' : '', text: t })))), tbody);
  const keyEl = h('ul', { class: 'key', 'aria-label': 'How to read the strips' },
    h('li', null, h('span', { class: 'strip', 'aria-hidden': 'true' }, h('i', { 'data-s': 'hit' })), document.createTextNode('KEV finding')),
    h('li', null, h('span', { class: 'strip', 'aria-hidden': 'true' }, h('i', { 'data-s': 'miss' })), document.createTextNode('non-KEV finding')));

  live.replaceChildren(
    h('h2', { class: 'vh', text: 'Weight bench' }),
    h('p', { class: 'bl-note' }, h('span', { class: 'label', text: 'Computed in your browser ' }),
      document.createTextNode('on the 20 synthetic sample findings; nothing is sent anywhere. Weights are relative: the score divides by their sum.')),
    h('p', { class: 'label', text: 'Presets' }), h('div', { class: 'bl-presets', role: 'group', 'aria-label': 'Weight presets' }, ...presetBtns),
    h('form', { class: 'wb-in' }, ...sliders.map((s) => s.box)),
    h('p', { class: 'wb-fl' }, h('span', { class: 'label', text: 'Score ' }), formula),
    h('h3', { class: 'wb-h', text: 'KEV findings in the top ' + TOP }), keyEl, counter, zeroNote,
    h('section', { class: 'scroll wb-scroll', tabindex: '0', 'aria-label': 'Ranked findings, scrolls sideways on narrow screens' }, table), status,
    h('p', { class: 'bl-prov label', text: 'kev-risk-prioritization ' + m.tag + ' at ' + m.commit + ' · synthetic data · ' + m.parity_cases + ' parity cases checked against the tool' }));
  render(true);
  stat.hidden = true;
  live.hidden = false;
}

if (typeof document !== 'undefined') init().catch(() => { /* leave the recorded static state visible */ });
