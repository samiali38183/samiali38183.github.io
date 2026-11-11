/* Lab explorer for the vulnlab page.
   It only displays recorded results (assets/data/vulnlab-bench.json, written by scripts/capture_vulnlab_bench.py from a real
   run of vulnlab v0.1.0). Nothing is evaluated here. If anything fails, the static record stays visible. */

const READING = {
  'true positive': 'Correct: the finding is the bug.',
  'false positive': 'False positive: this version is fixed.',
  missed: 'Not reported.',
  clean: 'Nothing to report on the fixed version.',
};

/* Pure part: what to show for one lab and one version. Used by the page and by scripts/test_bench_vulnlab.mjs. */
export function model(data, labId, verId) {
  const lab = data.labs.find((l) => l.id === labId);
  const v = lab.versions.find((x) => x.id === verId);
  const tags = {};
  for (const f of v.sinkline.findings) for (const s of f.flow) {
    const t = (tags[s.line] = tags[s.line] || []);
    if (t.indexOf(s.kind) < 0) t.push(s.kind);
  }
  const lines = v.code.replace(/\n$/, '').split('\n').map((text, i) => ({
    n: i + 1, text, bug: v.marks.bug.indexOf(i + 1) >= 0, changed: v.marks.changed.indexOf(i + 1) >= 0, tags: tags[i + 1] || [],
  }));
  const tests = v.tests.map((t) => ({
    name: t.name, role: data.roles[t.role], pass: t.passed === t.cases,
    result: (t.passed === t.cases ? 'Pass' : 'Fail') + (t.cases > 1 ? ' (' + t.passed + ' of ' + t.cases + ' cases)' : ''),
  }));
  const s = v.sinkline;
  const n = s.findings.length;
  const d = lab.detection;
  const sample = (key, label) => ({
    label, events: d[key].events, alerts: d[key].alerts, from: d[key].from,
    result: d[key].alerts ? 'Alert' : 'No alert', text: d[key].events + ' events, ' + d[key].alerts + ' alert' + (d[key].alerts === 1 ? '' : 's'),
  });
  const corr = d.correlation;
  const passed = v.tests.reduce((a, t) => a + t.passed, 0), cases = v.tests.reduce((a, t) => a + t.cases, 0);
  return {
    lab, v, lines, tests, tag: lab.n + ' ' + lab.title + ' (' + lab.cwe + ')',
    stamp: v.id === 'vulnerable' ? ['fail', 'Impact demonstrated'] : ['pass', 'Impact blocked'],
    testSummary: passed + ' of ' + cases + ' ' + (cases === 1 ? 'test case' : 'test cases') + ' passed in this version',
    sink: {
      command: s.command, out: s.out, stamp: n ? ['plain', 'Finding'] : ['off', 'No finding'], status: s.status,
      facts: (n ? s.findings.map((f) => f.rule_id + ', ' + f.cwe + ', ' + f.severity + ', app.py:' + f.line).join('; ') : 'no rule fired') + '. Exit status ' + s.status + '.',
      reading: READING[s.reading], note: s.note,
    },
    det: {
      rule: d.titles.join(' / ') + (corr ? ' (correlation: ' + corr.type + ' of ' + corr.field + ' by ' + corr.group_by + ', ' + corr.gte + ' or more in ' + corr.timespan + ')' : ''),
      samples: [sample('attack', 'Attack sample'), sample('benign', 'Benign sample')],
      out: d.attack.out + d.benign.out,
      test: d.test.name + ': ' + (d.test.passed === d.test.cases ? 'Pass' : 'Fail'),
    },
    spoken: lab.title + ', ' + v.label.toLowerCase() + ': ' + v.outcome + ' ' + (n ? 'sinkline: finding.' : 'sinkline: no finding.')
      + ' Detection: attack sample ' + d.attack.alerts + ' of ' + d.attack.events + ' alerts, benign sample ' + d.benign.alerts + '.',
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
  const state = { lab: data.labs[0].id, v: 'vulnerable' };
  const out = t('div', { class: 'vl-out' });
  const status = t('p', { class: 'vh', role: 'status' });
  const stamp = (s) => t('span', { class: 'stamp' + (s[0] === 'plain' ? '' : ' ' + s[0]), text: s[1] });
  const pre = (cls, label, body) => t('pre', { class: cls, 'data-label': label, tabindex: '0' }, [t('code', { text: body })]);
  const head = (text) => t('h2', { class: 'vl-h', text });
  const row = (cells, th) => t('tr', {}, cells.map((c, i) => t(i === 0 && th ? 'th' : 'td', th && i === 0 ? { scope: 'row' } : {}, [typeof c === 'string' ? doc.createTextNode(c) : c])));
  const table = (cls, cap, cols, rows) => t('table', { class: 'vl-tab ' + cls }, [
    t('caption', { text: cap }),
    t('thead', {}, [t('tr', {}, cols.map((c) => t('th', { scope: 'col', text: c })))]),
    t('tbody', {}, rows),
  ]);

  function show() {
    const m = model(data, state.lab, state.v);
    out.textContent = '';
    out.appendChild(t('p', { class: 'sw-verdict' }, [stamp(m.stamp), t('span', { class: 'vl-say', text: m.v.outcome })]));
    out.appendChild(t('p', { class: 'sw-note', text: m.v.summary }));

    out.appendChild(head('Service code'));
    out.appendChild(t('p', { class: 'sw-key', text: '! marks the vulnerable line the write-up names. + marks a line that is not in the vulnerable version. Tags after a line come from the recorded sinkline path.' }));
    const code = t('code');
    for (const l of m.lines) {
      const g = t('span', { class: 'g' });
      if (l.bug) g.appendChild(t('span', { class: 'k k-bug', text: 'bug' }));
      for (const k of l.tags) g.appendChild(t('span', { class: 'k k-' + k, text: k }));
      code.appendChild(t('span', { class: 'l' + (l.bug ? ' bg' : l.changed ? ' ch' : '') }, [
        t('span', { class: 'n', text: String(l.n) }),
        t('span', { class: 'd', text: l.bug ? '!' : l.changed ? '+' : '' }),
        t('span', { class: 'c', text: l.text }),
        g,
      ]));
    }
    const codePre = t('pre', { class: 'sw-code vl-code', 'data-label': m.v.file, tabindex: '0' }, [code]);
    out.appendChild(codePre);
    // bring the first marked line into view inside the scrolling pane (no tween)
    const first = [].slice.call(code.children).find((c) => (' ' + c.className + ' ').indexOf(' bg ') >= 0 || (' ' + c.className + ' ').indexOf(' ch ') >= 0);
    if (first && typeof first.offsetTop === 'number') codePre.scrollTop = Math.max(0, first.offsetTop - 64);

    out.appendChild(head('Tests'));
    out.appendChild(t('p', { class: 'sw-note', text: m.testSummary + '. From a recorded run of pytest -v; the detection test is listed under Detection.' }));
    out.appendChild(table('vl-tests', 'Recorded results of the tests that belong to this version', ['Test', 'What it shows', 'Result'],
      m.tests.map((x) => row([t('code', { text: x.name }), x.role, stamp([x.pass ? 'pass' : 'fail', x.result])], true))));

    out.appendChild(head('sinkline'));
    out.appendChild(t('p', { class: 'sw-verdict' }, [stamp(m.sink.stamp), t('span', { class: 'sw-facts', text: m.sink.facts })]));
    out.appendChild(t('p', { class: 'sw-note vl-read', text: m.sink.reading + (m.sink.note ? ' ' + m.sink.note : '') }));
    out.appendChild(pre('sw-out vl-sink', '$ ' + m.sink.command, m.sink.out));

    out.appendChild(head('Detection replay'));
    out.appendChild(t('p', { class: 'sw-note', text: 'Rule: ' + m.det.rule + '. ' + m.det.test + '.' }));
    out.appendChild(table('vl-det', 'The rule replayed over two recorded access logs', ['Sample', 'Events and alerts', 'Result'],
      m.det.samples.map((x) => row([x.label + ' (recorded from the ' + x.from + ' service)', x.text, stamp([x.result === 'Alert' ? 'plain' : 'off', x.result])], true))));
    out.appendChild(pre('sw-out vl-replay', '$ python -m vulnlab_common.replay RULE LOG', m.det.out));
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

  root.appendChild(group('vl-lab', 'Lab', data.labs.map((l) => ({ id: l.id, label: l.n + ' ' + l.title + ' (' + l.cwe + ')' })), 'lab'));
  root.appendChild(group('vl-ver', 'Version', data.labs[0].versions.map((v) => ({ id: v.id, label: v.label })), 'v'));
  root.appendChild(out);
  root.appendChild(status);
  show();
  return { state, show };
}

if (typeof document !== 'undefined') {
  const slot = document.querySelector('[data-bench="vulnlab"]');
  const live = slot && slot.querySelector('[data-bench-mount]');
  const stat = slot && slot.querySelector('.bench-static');
  if (live && stat) {
    fetch('/assets/data/vulnlab-bench.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((data) => {
        const app = mount(document, live, data);
        live.hidden = false;
        stat.hidden = true;
        app.show(); // again, now that the pane is laid out: scrolls the marked line into view
      })
      .catch(() => { live.textContent = ''; live.hidden = true; stat.hidden = false; });
  }
}
