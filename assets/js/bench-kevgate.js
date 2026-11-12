/* Control to evidence matrix for the kevgate page.
   It only displays recorded data (assets/data/kevgate-bench.json, written by scripts/capture_kevgate_bench.py from kevgate v0.1.1 and
   real CI runs). Nothing is evaluated here. If anything fails, the static table stays visible. */

const KINDS = { 'https://cyclonedx.org/bom': 'SBOM (CycloneDX)', 'https://sigstore.dev/cosign/sign/v1': 'signature (cosign)', 'https://slsa.dev/provenance/v1': 'provenance (SLSA)' };
const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');

/* Pure part: the strings shown for one control. Used by the page and by scripts/test_bench_kevgate.mjs. */
export function ref(d, x) {
  const more = x.end > x.start;
  return { text: x.path + ':' + x.start + (more ? '-' + x.end : ''), href: d.meta.repo + '/blob/' + d.meta.tag + '/' + x.path + '#L' + x.start + (more ? '-L' + x.end : '') };
}

export function rows(d, layer) {
  const label = Object.fromEntries(d.layers.map((l) => [l.id, l.label]));
  return d.controls.filter((c) => layer === 'all' || c.layer === layer).map((c) => ({
    id: c.id, title: c.title, layer: label[c.layer], code: c.code.length, tests: c.tests.length, ci: c.ci.length,
  }));
}

export function detail(d, c) {
  const label = Object.fromEntries(d.layers.map((l) => [l.id, l.label]));
  const src = (x) => x.src + ', line ' + x.line + (x.stride ? ' (' + x.stride + ')' : '');
  const doc = (x) => ({ text: x.text, src: src(x), href: d.meta.repo + '/blob/' + d.meta.tag + '/' + x.src + '#L' + x.line });
  return {
    title: c.title, layer: label[c.layer], threat: doc(c.threat), limits: c.limits.map(doc), note: c.note || '',
    code: c.code.map((x) => ref(d, x)),
    tests: c.tests.map((x) => ({ text: x.path + '::' + x.name + (x.cases > 1 ? ' (' + x.cases + ' cases)' : ''), href: ref(d, x).href })),
    ci: c.ci.map((s) => {
      const r = d.runs[s.wf];
      return {
        text: s.wf + ' / ' + s.job + ' / step ' + s.n + ': ' + s.step, href: d.meta.repo + '/actions/runs/' + r.id + '/job/' + s.job_id,
        run: r.id, runHref: d.meta.repo + '/actions/runs/' + r.id, state: s.conclusion === 'success' ? 'pass' : 'fail',
        word: s.conclusion === 'success' ? 'passed' : 'failed', date: r.date, step: ref(d, s.src), asserts: s.asserts.map((a) => ref(d, a)),
      };
    }),
    reg: c.registry ? 'Registry check on ' + d.meta.captured + ': ' + c.registry.image + ':' + c.registry.tag + ' resolves, with an anonymous token and no credentials, to '
      + c.registry.digest + '. Attached to that digest: ' + c.registry.attached.map((k) => KINDS[k] || k).join(', ') + '. The SBOM lists ' + c.registry.sbom_components
      + ' components; the SBOM and the provenance name that digest as their subject.' : '',
  };
}

export function spoken(d, layer, open) {
  const rs = rows(d, layer);
  const head = (layer === 'all' ? 'All layers' : rs[0].layer) + ': ' + plural(rs.length, 'control') + '.';
  const r = open && rs.find((x) => x.id === open);
  return head + (r ? ' Detail open for ' + r.title + ': ' + plural(r.tests, 'test') + ', ' + plural(r.ci, 'CI step') + '.' : '');
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
  const state = { layer: 'all', open: null };
  const body = t('tbody');
  const status = t('p', { class: 'vh', role: 'status' });
  const link = (text, href) => t('a', { href, text });
  /* `code` spans: the docs quote identifiers in backticks */
  const rich = (text) => text.split('`').map((s, i) => (i % 2 ? t('code', { text: s }) : doc.createTextNode(s)));
  const list = (items) => t('ul', { class: 'kg-list' }, items.map((x) => t('li', {}, x)));
  const head = (text) => t('h3', { class: 'kg-h', text });
  const chip = (x) => t('a', { class: 'chip', 'data-s': x.state, href: x.runHref }, [
    t('span', { class: 'st', 'aria-hidden': 'true' }), t('span', { text: 'run ' + x.run }), doc.createTextNode(' '), t('span', { class: 'd', text: x.word + ' ' + x.date })]);

  function panel(c) {
    const m = detail(data, c);
    const kids = [t('h2', { class: 'kg-t', id: 'kg-title', text: m.title }), t('p', { class: 'label', text: 'Layer: ' + m.layer })];
    const quote = (x) => [t('blockquote', {}, [t('p', {}, rich(x.text))]), t('p', { class: 'kg-src' }, [doc.createTextNode('Source: '), link(x.src, x.href)])];
    kids.push(head('Threat, in the repository’s words'), ...quote(m.threat));
    kids.push(head('Implemented at'), list(m.code.map((x) => [link(x.text, x.href)])));
    if (m.tests.length) kids.push(head('Evidence: tests'), list(m.tests.map((x) => [link(x.text, x.href)])));
    kids.push(head('Evidence: CI steps'), list(m.ci.map((x) => {
      const out = [link(x.text, x.href), doc.createTextNode(' '), chip(x), t('br'), doc.createTextNode('Step defined at '), link(x.step.text, x.step.href)];
      if (x.asserts.length) {
        out.push(doc.createTextNode('; asserts at '));
        x.asserts.forEach((a, i) => { if (i) out.push(doc.createTextNode(', ')); out.push(link(a.text, a.href)); });
      }
      return out;
    })));
    if (m.reg) kids.push(t('p', { class: 'kg-src', text: m.reg }));
    kids.push(head('Limitation, from the docs'), ...m.limits.flatMap(quote));
    if (m.note) kids.push(t('p', { class: 'kg-src' }, rich(m.note)));
    kids.push(t('button', { type: 'button', class: 'kg-close', text: 'Close detail' }));
    const sec = t('section', { class: 'kg-detail', id: 'kg-detail', 'aria-labelledby': 'kg-title', tabindex: '-1' }, kids);
    sec.lastChild.addEventListener('click', () => select(c.id, true));
    return sec;
  }

  function render(focusId) {
    body.textContent = '';
    for (const r of rows(data, state.layer)) {
      const open = state.open === r.id;
      const b = t('button', { type: 'button', class: 'kg-pick', 'aria-expanded': String(open), 'aria-controls': 'kg-detail', text: r.title });
      b.addEventListener('click', () => select(r.id, false));
      const cell = (label, v, cls) => t('td', { 'data-label': label, class: cls || '' }, [typeof v === 'string' ? doc.createTextNode(v) : v]);
      body.appendChild(t('tr', open ? { class: 'kg-on' } : {}, [
        t('th', { scope: 'row' }, [b]), cell('Layer', r.layer), cell('Code', String(r.code), 'num'), cell('Tests', String(r.tests), 'num'), cell('CI steps', String(r.ci), 'num')]));
      if (open) {
        body.appendChild(t('tr', { class: 'kg-row' }, [t('td', { colspan: '5' }, [panel(data.controls.find((c) => c.id === r.id))])]));
      }
      if (focusId === r.id && b.focus) b.focus();
    }
    status.textContent = spoken(data, state.layer, state.open);
  }

  function select(id, toggleOff) {
    state.open = toggleOff || state.open === id ? null : id;
    render(id);
  }

  const fs = t('fieldset', { class: 'sw-pick' }, [t('legend', { text: 'Layer' })]);
  const opts = t('div', { class: 'sw-opts' });
  fs.appendChild(opts);
  const layers = [{ id: 'all', label: 'All' }].concat(data.layers);
  for (const l of layers) {
    const n = rows(data, l.id).length;
    const input = t('input', { type: 'radio', name: 'kg-layer', value: l.id });
    input.checked = l.id === state.layer;
    if (input.checked) input.setAttribute('checked', '');
    input.addEventListener('change', () => {
      if (!input.checked) return;
      state.layer = l.id;
      if (state.open && !rows(data, l.id).some((r) => r.id === state.open)) state.open = null;
      render();
    });
    opts.appendChild(t('label', {}, [input, t('span', { text: l.label + ' (' + n + ')' })]));
  }
  const table = t('table', { class: 'tbl kg-tab' }, [
    t('caption', { text: 'Controls, and how many code locations, tests and CI steps cite each one. Select a control name to open its detail.' }),
    t('thead', {}, [t('tr', {}, ['Control', 'Layer', 'Code', 'Tests', 'CI steps'].map((x) => t('th', { scope: 'col', text: x })))]), body]);
  root.appendChild(fs);
  root.appendChild(t('div', { class: 'scroll kg-scroll' }, [table]));
  root.appendChild(status);
  root.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.open) { const id = state.open; state.open = null; render(id); }
  });
  render();
  return { state, render };
}

if (typeof document !== 'undefined') {
  const slot = document.querySelector('[data-bench="kevgate"]');
  const live = slot && slot.querySelector('[data-bench-mount]');
  const stat = slot && slot.querySelector('.bench-static');
  if (live && stat) {
    fetch('/assets/data/kevgate-bench.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((data) => {
        mount(document, live, data);
        live.hidden = false;
        stat.hidden = true;
      })
      .catch(() => { live.textContent = ''; live.hidden = true; stat.hidden = false; });
  }
}
