/* Admission desk for the kevgate-admit page.
   It only displays AdmissionReview responses recorded from a running kevgate-admit v0.1.0
   (assets/data/admission-bench.json, written by scripts/capture_admission_bench.py). No policy code runs here.
   If anything fails, the static record stays visible. */

const STAMP = { allowed: ['pass', 'Allowed'], denied: ['fail', 'Denied'], warned: ['limit', 'Allowed with warning'] };

/* Pure part. Used by the page and by scripts/test_bench_admission.mjs. */
export function verdict(raw) {
  const r = raw.response;
  return !r.allowed ? 'denied' : r.warnings && r.warnings.length ? 'warned' : 'allowed';
}

export function record(data, view, a, b) {
  return view === 'signed'
    ? data.signed.results.find((r) => r.image === a && r.state === b)
    : data.results.find((r) => r.image === a && r.policy === b);
}

export function model(data, view, a, b) {
  if (view === 'scanner') {
    const s = data.scanner, p = s.parser;
    return {
      view, spoken: 'Scanner report: ' + p.findings.length + ' findings parsed from ' + s.raw_entries + ' entries.',
      head: 'Trivy ' + s.trivy + ' report, target ' + s.target + ': ' + s.raw_entries + ' vulnerability entries, parsed into ' + p.findings.length + ' findings.',
      rows: p.findings.map((f) => [f.ID, f.Package, f.Installed, f.Fixed || 'no fix', f.Severity, f.CVSS.toFixed(1), f.EPSS == null ? 'none' : String(f.EPSS), f.Risk.toFixed(1)]),
      note: s.scored_with + '. The fixture is ' + s.fixture + ', ' + s.bytes + ' bytes, trimmed by the repository from a longer report.',
    };
  }
  const rec = record(data, view, a, b);
  const resp = rec.raw.response, v = verdict(rec.raw);
  const img = data.images.find((i) => i.id === a);
  const signed = view === 'signed';
  const pol = signed ? null : data.policies.find((p) => p.id === b);
  const ns = signed ? data.signed.namespace : pol.namespace;
  const scope = signed ? data.signed.scope : pol.scope;
  const msg = resp.status ? resp.status.message : '';
  const where = signed ? data.signed.states.find((s) => s.id === b).label.toLowerCase() : pol.label;
  const rules = rec.rules.join(', ');
  return {
    view, v, stamp: STAMP[v], message: msg, warnings: resp.warnings || [], findings: rec.findings,
    worked: rec.findings.filter((f, i, all) => all.findIndex((g) => g.cve === f.cve) === i).map((f) => f.cve + ': ' + f.worked),
    formula: data.provenance.formula,
    rules: v === 'denied' ? 'Rule fired: ' + rules : v === 'warned' ? 'Would have fired, admitted in audit mode: ' + rules : 'No rule fired',
    request: img.ref + ' in namespace ' + ns + ' (scope ' + scope + ')',
    policy: signed ? 'Policy requireSignedEvidence. Report store: ' + data.signed.states.find((s) => s.id === b).edit : pol.summary,
    code: resp.status ? String(resp.status.code) : '',
    raw: JSON.stringify(rec.raw, null, 2),
    spoken: img.label + ', ' + where + ': ' + STAMP[v][1].toLowerCase() + '. ' + (rec.rules.length ? 'Rules: ' + rules + '.' : 'No rule fired.'),
  };
}

/* DOM part. `doc` is injected so the test can run it against a stub. */
function h(doc, tag, props, kids) {
  const e = doc.createElement(tag);
  for (const k in props || {}) {
    if (k === 'text') e.textContent = props[k];
    else e.setAttribute(k, props[k]);
  }
  for (const c of kids || []) e.appendChild(c);
  return e;
}

export function mount(doc, root, data) {
  const t = (tag, props, kids) => h(doc, tag, props, kids);
  const S = { view: 'decision', img: 'clean', pol: 'enforce', simg: 'clean', st: 'valid' };
  const out = t('div', { class: 'ad-out' });
  const status = t('p', { class: 'vh', role: 'status' });
  const boxes = {};

  function group(box, name, legend, items, key) {
    const opts = t('div', { class: 'sw-opts' });
    const fs = t('fieldset', { class: 'sw-pick' }, [t('legend', { text: legend }), opts]);
    for (const it of items) {
      const input = t('input', { type: 'radio', name, value: it.id });
      input.checked = it.id === S[key];
      if (input.checked) input.setAttribute('checked', '');
      input.addEventListener('change', () => { if (input.checked) { S[key] = it.id; show(); } });
      opts.appendChild(t('label', {}, [input, t('span', { text: it.label })]));
    }
    box.appendChild(fs);
  }

  function pre(label, text) {
    return t('pre', { 'data-label': label, tabindex: '0' }, [t('code', { text })]);
  }

  function table(caption, cols, rows) {
    const body = t('tbody');
    for (const r of rows) body.appendChild(t('tr', {}, r.map((c, i) => (i === 0 ? t('th', { scope: 'row', text: c }) : t('td', { text: c, class: /^[\d.]+$/.test(c) ? 'num' : '' })))));
    return t('section', { class: 'scroll', tabindex: '0', 'aria-label': caption + ', scrolls sideways on narrow screens' }, [t('table', { class: 'ad-tab' }, [
      t('caption', { text: caption }),
      t('thead', {}, [t('tr', {}, cols.map((c) => t('th', { scope: 'col', text: c })))]),
      body,
    ])]);
  }

  function show() {
    const signed = S.view === 'signed';
    boxes.decision.hidden = S.view !== 'decision';
    boxes.signed.hidden = !signed;
    const m = S.view === 'scanner' ? model(data, 'scanner') : signed ? model(data, 'signed', S.simg, S.st) : model(data, 'decision', S.img, S.pol);
    out.textContent = '';
    if (m.view === 'scanner') {
      out.appendChild(t('p', { class: 'ad-req', text: m.head }));
      out.appendChild(table('Findings as parsed by trivy.Parse', ['CVE', 'Package', 'Installed', 'Fixed in', 'Severity', 'CVSS', 'EPSS', 'Risk'], m.rows));
      out.appendChild(t('p', { class: 'ad-req', text: m.note }));
    } else {
      out.appendChild(t('p', { class: 'sw-verdict' }, [t('span', { class: 'stamp ' + m.stamp[0], text: m.stamp[1] }), doc.createTextNode(' '), t('span', { class: 'sw-facts', text: m.rules })]));
      out.appendChild(t('p', { class: 'ad-req' }, [t('span', { text: 'Request: ' }), t('code', { text: m.request }), t('span', { text: '. Policy: ' + m.policy })]));
      if (m.message) out.appendChild(pre('status.message (' + m.code + ')', m.message));
      if (m.warnings.length) out.appendChild(pre('warnings (allowed)', m.warnings.join('\n')));
      if (!m.message && !m.warnings.length) out.appendChild(t('p', { class: 'ad-req', text: 'The response carries no message and no warnings.' }));
      if (m.findings.length) {
        out.appendChild(table('Findings listed in the denial text', ['Rule', 'CVE', 'In KEV', 'Risk', 'Package'], m.findings.map((f) => [f.rule, f.cve, f.kev ? 'KEV' : 'no', f.risk.toFixed(1), f.pkg])));
        out.appendChild(t('p', { class: 'ad-req', text: m.formula + ' (acr 4 is the default asset criticality):' }));
        out.appendChild(t('ul', { class: 'ad-w' }, m.worked.map((w) => t('li', {}, [t('code', { text: w })]))));
      }
      out.appendChild(t('details', { class: 'alt' }, [t('summary', { text: 'Raw AdmissionReview response' }), pre('POST /validate response', m.raw)]));
    }
    status.textContent = m.spoken;
  }

  root.appendChild(t('p', { class: 'sw-lead', text: 'Recorded, not live. Each result is a response that a running kevgate-admit v0.1.0 returned; nothing is evaluated in your browser.' }));
  const vbox = t('div');
  group(vbox, 'ad-view', 'View', [{ id: 'decision', label: 'Admission decision' }, { id: 'signed', label: 'Signed evidence' }, { id: 'scanner', label: 'Scanner report' }], 'view');
  root.appendChild(vbox);
  boxes.decision = t('div');
  group(boxes.decision, 'ad-img', 'Workload image', data.images.map((i) => ({ id: i.id, label: i.label })), 'img');
  group(boxes.decision, 'ad-pol', 'Namespace policy', data.policies.map((p) => ({ id: p.id, label: p.label })), 'pol');
  boxes.signed = t('div');
  group(boxes.signed, 'ad-simg', 'Workload image', data.signed.images.map((id) => ({ id, label: data.images.find((i) => i.id === id).label })), 'simg');
  group(boxes.signed, 'ad-st', 'Report store', data.signed.states.map((s) => ({ id: s.id, label: s.label })), 'st');
  root.appendChild(boxes.decision);
  root.appendChild(boxes.signed);
  root.appendChild(out);
  root.appendChild(status);
  show();
  return { S, show };
}

if (typeof document !== 'undefined') {
  const slot = document.querySelector('[data-bench="kevgate-admit"]');
  const live = slot && slot.querySelector('[data-bench-mount]');
  const stat = slot && slot.querySelector('.bench-static');
  if (live && stat) {
    fetch('/assets/data/admission-bench.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((data) => {
        mount(document, live, data);
        live.hidden = false;
        stat.hidden = true;
      })
      .catch(() => { live.textContent = ''; live.hidden = true; stat.hidden = false; });
  }
}
