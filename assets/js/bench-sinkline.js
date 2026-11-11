/* Sanitizer switch for the sinkline page.
   It only displays recorded output of `sinkline scan` (assets/data/bench-sinkline.json, written by
   scripts/capture_sinkline_bench.py). No analysis happens here. If anything fails, the static record stays visible. */

/* Pure part: what to show for one example and one variant. Used by the page and by scripts/test_bench_sinkline.mjs. */
export function model(data, exId, varId) {
  const ex = data.examples.find((e) => e.id === exId);
  const v = ex.variants.find((x) => x.id === varId);
  const f = v.findings[0] || null;
  const tags = {};
  if (f) for (const s of f.route) {
    const t = (tags[s.line] = tags[s.line] || []);
    if (t.indexOf(s.kind) < 0) t.push(s.kind);
  }
  const lines = v.code.replace(/\n$/, '').split('\n').map((text, i) => ({
    n: i + 1, text, changed: v.changed.indexOf(i + 1) >= 0, tags: tags[i + 1] || [],
  }));
  const san = f ? f.route.find((s) => s.kind === 'sanitizer') : null;
  return {
    file: v.file, lines, out: v.out, status: v.status, found: !!f,
    command: data.provenance.command.replace('FILE', v.file),
    stamp: f ? ['fail', 'Finding'] : ['pass', 'No finding'],
    facts: f ? f.rule_id + ', ' + f.cwe + ', ' + f.severity + ', confidence ' + f.confidence : 'no rule fired',
    sanitizer: san ? 'Recorded sanitizer step: ' + san.note + '. The finding is ' + f.cwe + '.' : '',
    spoken: ex.title + ', ' + v.label.toLowerCase() + ': ' + (f ? 'finding ' + f.rule_id + ', ' + f.cwe : 'no finding') + '. Exit status ' + v.status + '.',
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
  const state = { ex: data.examples[0].id, v: 'unsafe' };
  const status = t('p', { class: 'vh', role: 'status' });
  const stampEl = t('span', { class: 'stamp' });
  const factsEl = t('span', { class: 'sw-facts' });
  const noteEl = t('p', { class: 'sw-note' });
  const codeEl = t('code');
  const outEl = t('code');
  const codePre = t('pre', { class: 'sw-code', tabindex: '0' }, [codeEl]);
  const outPre = t('pre', { class: 'sw-out', tabindex: '0' }, [outEl]);

  function show() {
    const m = model(data, state.ex, state.v);
    codePre.setAttribute('data-label', m.file);
    outPre.setAttribute('data-label', '$ ' + m.command);
    codeEl.textContent = '';
    for (const l of m.lines) {
      const tagBox = t('span', { class: 'g' });
      for (const k of l.tags) tagBox.appendChild(t('span', { class: 'k k-' + k, text: k }));
      codeEl.appendChild(t('span', { class: 'l' + (l.changed ? ' ch' : '') }, [
        t('span', { class: 'n', text: String(l.n) }),
        t('span', { class: 'd', text: l.changed ? '+' : '' }),
        t('span', { class: 'c', text: l.text }),
        tagBox,
      ]));
    }
    outEl.textContent = m.out;
    stampEl.className = 'stamp ' + m.stamp[0];
    stampEl.textContent = m.stamp[1];
    factsEl.textContent = m.facts + '. Exit status ' + m.status + '.';
    noteEl.textContent = m.sanitizer;
    noteEl.hidden = !m.sanitizer;
    status.textContent = m.spoken;
  }

  function group(name, legend, items, key) {
    const box = t('div', { class: 'sw-opts' });
    const fs = t('fieldset', { class: 'sw-pick' }, [t('legend', { text: legend }), box]);
    for (const it of items) {
      const input = t('input', { type: 'radio', name, value: it.id });
      if (it.id === state[key]) input.setAttribute('checked', '');
      input.checked = it.id === state[key];
      input.addEventListener('change', () => { if (input.checked) { state[key] = it.id; show(); } });
      box.appendChild(t('label', {}, [input, t('span', { text: it.label })]));
    }
    return fs;
  }

  const exItems = data.examples.map((e) => ({ id: e.id, label: e.title + ' (' + e.cwe + ')' }));
  const vItems = data.examples[0].variants.map((v) => ({ id: v.id, label: v.label }));
  root.appendChild(group('sw-ex', 'Bug class', exItems, 'ex'));
  root.appendChild(group('sw-var', 'Version of the code', vItems, 'v'));
  root.appendChild(t('p', { class: 'sw-key', text: 'A + marks a line that differs from the unsafe version. Tags after a line come from the recorded path: source, propagate, sanitizer, sink.' }));
  root.appendChild(codePre);
  root.appendChild(t('p', { class: 'sw-verdict' }, [stampEl, doc.createTextNode(' '), factsEl]));
  root.appendChild(noteEl);
  root.appendChild(outPre);
  root.appendChild(status);
  show();
  return { state, show };
}

if (typeof document !== 'undefined') {
  const slot = document.querySelector('[data-bench="sinkline"]');
  const live = slot && slot.querySelector('[data-bench-mount]');
  const stat = slot && slot.querySelector('.bench-static');
  if (live && stat) {
    fetch('/assets/data/bench-sinkline.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((data) => {
        mount(document, live, data);
        live.hidden = false;
        stat.hidden = true;
      })
      .catch(() => { live.textContent = ''; live.hidden = true; stat.hidden = false; });
  }
}
