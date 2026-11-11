/* Side-by-side parser for the fuzzdiff sheet.
   It only displays recorded results (assets/data/fuzzdiff-bench.json, written by scripts/capture_fuzzdiff_bench.py):
   what picohttpparser (C), fuzzdiff (Rust) and httparse returned for each input, and how the fuzzdiff harness
   classified the pair. Nothing is parsed in the browser. If anything fails, the static table stays visible. */

const SHOW = 240; // characters of the escaped bytes shown

/* Pure part: text for one result. scripts/bench_static.py formats the same strings for the no-JS table,
   and scripts/test_bench_fuzzdiff.mjs checks that both equal each other and the JSON. */
export function resultLines(r, op) {
  if (!r) return ['not run (see the note)'];
  if (r.verdict === 'partial') return ['partial (needs more bytes)'];
  if (r.verdict === 'panic') return ['panic (the parser panicked)'];
  if (r.verdict === 'error') return ['error' + (r.error ? ' (' + r.error + ')' : '')];
  if (op === 'chunked') {
    if ('size' in r) return ['complete (size line ' + r.consumed + ' bytes, size ' + r.size + ')'];
    return ['complete', 'decoded "' + r.decoded + '" (' + r.decoded_len + ' bytes)', 'leftover "' + r.leftover + '" (' + r.leftover_len + ' bytes)'];
  }
  const out = ['complete (consumed ' + r.consumed + ' bytes)'];
  if (op === 'request') out.push('method "' + r.method + '", target "' + r.target + '", HTTP/1.' + r.minor);
  if (op === 'response') out.push('HTTP/1.' + r.minor + ', status ' + r.status + ', reason "' + r.reason + '"');
  out.push(r.nheaders + (r.nheaders === 1 ? ' header' : ' headers'));
  for (const h of r.headers) out.push((h[0] === null ? '(no name)' : h[0]) + ': ' + h[1]);
  if (r.nheaders > r.headers.length) out.push('+' + (r.nheaders - r.headers.length) + ' more');
  return out;
}

export function shownBytes(i) {
  return i.bytes.length > SHOW ? { text: i.bytes.slice(0, SHOW) + '…', note: 'First ' + SHOW + ' characters of the escaped bytes shown; ' + i.bytes_len + ' bytes in total.' }
    : { text: i.bytes, note: '' };
}

export function harnessView(i) {
  const h = i.harness;
  if (h.kind === 'Equal') return { kind: 'pass', label: 'Equal', text: 'C and Rust returned the same result.' };
  if (h.kind === 'BothReject') return { kind: 'plain', label: 'BothReject', text: 'Both rejected the input.' };
  if (h.kind === 'RustStricter') return { kind: 'limit', label: 'RustStricter (' + h.deviation + ')', text: 'Rust rejects what C accepts, by a documented deviation (D1: optional rejection of folded header lines, switched on for this input).' };
  return { kind: 'fail', label: 'Divergence (' + h.how + ')', text: 'The two results differ, so the harness reports a bug. Here the bug is the seeded one named in the title.' };
}

export function httparseView(i) {
  if (i.mutant) return 'Shown for reference only. The seeded bug is in the Rust column, so no pattern is classified.';
  if (i.pattern === null) return '';
  const base = 'Pattern ' + i.pattern + ' (picohttpparser, fuzzdiff, httparse; C complete, P partial, R reject; ! fields differ). ';
  if (i.doc) {
    const tail = i.doc.stricter === 'same' ? 'The three parsers behave alike here.' : 'Stricter: ' + i.doc.stricter + '.';
    return base + 'Documented class: ' + i.doc.class + ' (' + i.doc.rfc + '). ' + tail + (i.strict ? ' The pattern is for the default configuration; this input runs Rust in strict mode.' : '');
  }
  if (i.explained_by === 'agree') return base + 'All three agree.';
  return base + 'Explained by ' + i.explained_by + '.';
}

export function model(data, id) {
  const i = data.inputs.find((x) => x.id === id);
  const b = shownBytes(i);
  const hp = i.op === 'chunked' ? 'httparse ' + data.meta.httparse.split(' ')[0] + ', parse_chunk_size (first line only)' : 'httparse ' + data.meta.httparse.split(' ')[0];
  const hv = harnessView(i);
  return {
    id: i.id, title: i.title, group: i.group, source: i.source.ref, op: i.op,
    bytes: b.text, bytesNote: b.note, bytesLen: i.bytes_len,
    cols: [
      { key: 'c', name: 'picohttpparser (C, ' + data.meta.c_reference.split(' ')[1] + ')', lines: resultLines(i.c, i.op) },
      { key: 'rust', name: 'fuzzdiff (Rust)' + (i.mutant ? ' with ' + i.mutant + ' switched on' : '') + (i.strict ? ', strict mode' : ''), lines: resultLines(i.rust, i.op) },
      { key: 'hp', name: hp, lines: resultLines(i.httparse, i.op) },
    ],
    stamp: [hv.kind, hv.label], harness: hv.text, relation: httparseView(i),
    spoken: i.title + '. Harness: ' + hv.label + '. C: ' + resultLines(i.c, i.op)[0] + '. Rust: ' + resultLines(i.rust, i.op)[0] + '. httparse: ' + resultLines(i.httparse, i.op)[0] + '.',
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
  const state = { id: data.inputs[0].id };
  const status = t('p', { class: 'vh', role: 'status' });
  const title = t('h3', { class: 'fz-title' });
  const meta = t('p', { class: 'fz-meta' });
  const bytesCode = t('code');
  const bytesPre = t('pre', { class: 'fz-bytes', tabindex: '0' }, [bytesCode]);
  const bytesNote = t('p', { class: 'fz-note' });
  const cols = ['c', 'rust', 'hp'].map((k) => {
    const name = t('h4', { class: 'fz-cn' });
    const body = t('div', { class: 'fz-res' });
    return { k, name, body, el: t('div', { class: 'fz-col', 'data-col': k }, [name, body]) };
  });
  const stampEl = t('span', { class: 'stamp' });
  const harnessEl = t('span', { class: 'fz-htext' });
  const relEl = t('p', { class: 'fz-rel' });

  function show() {
    const m = model(data, state.id);
    title.textContent = m.title;
    meta.textContent = m.group + ' · ' + m.op + ' entry point · ' + m.bytesLen + ' bytes · source: ' + m.source;
    bytesPre.setAttribute('data-label', 'bytes, escapes shown');
    bytesCode.textContent = m.bytes;
    bytesNote.textContent = m.bytesNote;
    bytesNote.hidden = !m.bytesNote;
    m.cols.forEach((c, n) => {
      cols[n].name.textContent = c.name;
      cols[n].body.textContent = '';
      for (const l of c.lines) cols[n].body.appendChild(t('p', { text: l }));
    });
    stampEl.className = 'stamp ' + (m.stamp[0] === 'plain' ? '' : m.stamp[0]);
    stampEl.textContent = m.stamp[1];
    harnessEl.textContent = m.harness;
    relEl.textContent = m.relation;
    relEl.hidden = !m.relation;
    status.textContent = m.spoken;
  }

  // picker: one radio group (arrow keys move through every input), shown in a fieldset per entry point
  const picker = t('div', { class: 'fz-pick' });
  const groups = [];
  for (const i of data.inputs) if (groups.indexOf(i.group) < 0) groups.push(i.group);
  const radios = [];
  for (const g of groups) {
    const box = t('div', { class: 'sw-opts' });
    picker.appendChild(t('fieldset', { class: 'sw-pick' }, [t('legend', { text: g }), box]));
    for (const i of data.inputs.filter((x) => x.group === g)) {
      const input = t('input', { type: 'radio', name: 'fz-input', value: i.id });
      if (i.id === state.id) input.setAttribute('checked', '');
      input.checked = i.id === state.id;
      input.addEventListener('change', () => { if (input.checked) { state.id = i.id; show(); } });
      radios.push(input);
      box.appendChild(t('label', {}, [input, t('span', { text: i.title })]));
    }
  }

  root.appendChild(t('h2', { class: 'vh', text: 'Side-by-side parser' }));
  root.appendChild(t('p', { class: 'sw-lead', text: 'Recorded, not live. Pick an input to see what each parser returned. Nothing is parsed in your browser.' }));
  root.appendChild(picker);
  root.appendChild(title);
  root.appendChild(meta);
  root.appendChild(bytesPre);
  root.appendChild(bytesNote);
  root.appendChild(t('div', { class: 'fz-cols' }, cols.map((c) => c.el)));
  root.appendChild(t('p', { class: 'fz-verdict' }, [t('span', { class: 'fz-hl', text: 'Harness classification' }), stampEl, harnessEl]));
  root.appendChild(relEl);
  root.appendChild(status);
  show();
  return { state, show, radios };
}

if (typeof document !== 'undefined') {
  const slot = document.querySelector('[data-bench="fuzzdiff"]');
  const live = slot && slot.querySelector('[data-bench-mount]');
  const stat = slot && slot.querySelector('.bench-static');
  if (live && stat) {
    fetch('/assets/data/fuzzdiff-bench.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((data) => {
        mount(document, live, data);
        live.hidden = false;
        stat.hidden = true;
      })
      .catch(() => { live.textContent = ''; live.hidden = true; stat.hidden = false; });
  }
}
