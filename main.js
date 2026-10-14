/* Desktop window manager + app launch sequence */
(function () {
  'use strict';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const simple = document.documentElement.classList.contains('simple');

  const desk = $('#desk');
  const splash = $('#splash');
  const splashName = $('#splashName');
  const splashSub = $('#splashSub');
  const splashBar = $('#splashBar');
  const splashIco = $('#splashIco');
  const appMenu = $('#appMenu');
  const clockEl = $('#clock');
  const tasks = $('#tasks');
  let z = 20, drag = null, resize = null, launching = false;

  const META = {
    about: { title: 'About', bin: 'about', logs: ['reading ~/.profile', 'loading internships', 'ready'] },
    projects: { title: 'Projects', bin: 'files', logs: ['mounting /home/sami/projects', 'indexing 6 files', 'ready'] },
    resume: { title: 'Resume', bin: 'evince', logs: ['opening resume.pdf', 'rendering pages', 'ready'] },
    contact: { title: 'Mail', bin: 'thunderbird', logs: ['starting mail', 'loading compose', 'ready'] },
    term: { title: 'Terminal', bin: 'qterminal', logs: ['allocating pty', 'bash 5.2', 'ready'] },
    files: { title: 'Files', bin: 'thunar', logs: ['opening home', 'ready'] },
    lab: { title: 'agent-lab.md', bin: 'mousepad', logs: ['opening markdown', 'ready'] },
    'call-kettle': { title: 'call-kettle.md', bin: 'mousepad', logs: ['opening markdown', 'ready'] },
    kev: { title: 'kev.md', bin: 'mousepad', logs: ['opening case study', 'ready'] },
    'power-bi': { title: 'power-bi.md', bin: 'mousepad', logs: ['opening notes', 'ready'] },
    wireshark: { title: 'wireshark.md', bin: 'mousepad', logs: ['opening lab', 'ready'] },
    phish: { title: 'phishing-ioc.md', bin: 'mousepad', logs: ['opening notes', 'ready'] },
    trash: { title: 'Trash', bin: 'trash', logs: ['checking trash', 'empty'] }
  };

  function clock() {
    const d = new Date();
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    clockEl.textContent = days[d.getDay()] + ' ' + d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
  }
  clock();
  setInterval(clock, 10000);

  function winEl(id) { return document.querySelector('.win[data-id="' + id + '"]'); }

  function focusWin(id) {
    const el = winEl(id);
    if (!el) return;
    z += 1;
    el.style.zIndex = String(z);
    $$('.win').forEach((w) => w.classList.toggle('is-focus', w === el));
    $$('.task').forEach((t) => t.classList.toggle('is-on', t.dataset.id === id));
  }

  function renderTasks() {
    if (!tasks) return;
    tasks.innerHTML = '';
    $$('.win.is-open').forEach((w) => {
      if (w.classList.contains('is-min')) return;
      const b = document.createElement('button');
      b.className = 'task' + (w.classList.contains('is-focus') ? ' is-on' : '');
      b.dataset.id = w.dataset.id;
      b.textContent = w.dataset.title;
      b.addEventListener('click', () => {
        w.classList.remove('is-min');
        w.classList.add('is-open');
        focusWin(w.dataset.id);
      });
      tasks.appendChild(b);
    });
  }

  function place(el) {
    if (simple) {
      el.classList.add('is-max');
      el.style.left = '0'; el.style.top = '0';
      el.style.width = '100%'; el.style.height = '100%';
      return;
    }
    if (el.dataset.placed) return;
    const n = $$('.win.is-open').length;
    el.style.left = (48 + (n * 28) % 200) + 'px';
    el.style.top = (36 + (n * 24) % 140) + 'px';
    el.style.width = el.dataset.w || '540px';
    el.style.height = el.dataset.h || '380px';
    el.dataset.placed = '1';
  }

  function openWin(id) {
    const el = winEl(id);
    if (!el) return;
    if (simple) {
      $$('.win').forEach((w) => {
        if (w !== el) w.classList.remove('is-open', 'is-min', 'is-max', 'is-focus');
      });
    }
    el.classList.add('is-open');
    el.classList.remove('is-min');
    place(el);
    focusWin(id);
    renderTasks();
    if (id === 'term') setTimeout(() => $('#termInput')?.focus(), 40);
  }

  function closeWin(id) {
    const el = winEl(id);
    if (!el) return;
    el.classList.remove('is-open', 'is-min', 'is-max', 'is-focus');
    renderTasks();
  }

  function launch(id, fromEl) {
    if (id === 'resume-file') {
      const a = document.createElement('a');
      a.href = 'resume.pdf'; a.download = 'Sami-Ali-Resume.pdf'; a.click();
      return;
    }
    const meta = META[id] || { title: id, bin: id, logs: ['starting', 'ready'] };
    if (reduce) { openWin(id); return; }
    if (launching) return;
    launching = true;
    fromEl?.classList.add('is-launch');
    setTimeout(() => fromEl?.classList.remove('is-launch'), 400);

    const ico = fromEl?.querySelector('.ico');
    splashIco.innerHTML = ico ? ico.outerHTML : '';
    splashName.textContent = meta.title;
    splashSub.textContent = 'starting ' + meta.bin + '…';
    splashBar.style.width = '0%';
    splash.classList.add('is-on');

    const logs = meta.logs;
    const total = simple ? 520 : 780;
    const t0 = performance.now();
    function tick(now) {
      const p = Math.min(1, (now - t0) / total);
      splashBar.style.width = Math.round(p * 100) + '%';
      const li = Math.min(logs.length - 1, Math.floor(p * logs.length));
      splashSub.textContent = logs[li];
      if (p < 1) requestAnimationFrame(tick);
      else {
        splash.classList.remove('is-on');
        launching = false;
        openWin(id);
      }
    }
    requestAnimationFrame(tick);
  }

  $$('.win').forEach((el) => {
    el.addEventListener('mousedown', () => focusWin(el.dataset.id));
    el.querySelector('[data-act="x"]')?.addEventListener('click', (e) => { e.stopPropagation(); closeWin(el.dataset.id); });
    el.querySelector('[data-act="m"]')?.addEventListener('click', (e) => { e.stopPropagation(); el.classList.add('is-min'); el.classList.remove('is-focus'); renderTasks(); });
    el.querySelector('[data-act="M"]')?.addEventListener('click', (e) => { e.stopPropagation(); el.classList.toggle('is-max'); focusWin(el.dataset.id); });
    el.querySelector('.titlebar')?.addEventListener('dblclick', () => { if (!simple) el.classList.toggle('is-max'); });
    el.querySelector('.titlebar')?.addEventListener('mousedown', (e) => {
      if (simple || e.button !== 0 || e.target.closest('.ctrl') || el.classList.contains('is-max')) return;
      const r = el.getBoundingClientRect();
      const wr = desk.getBoundingClientRect();
      drag = { el, dx: e.clientX - r.left, dy: e.clientY - r.top, wr };
      e.preventDefault();
    });
    el.querySelector('.rsz')?.addEventListener('mousedown', (e) => {
      if (simple) return;
      e.stopPropagation();
      const r = el.getBoundingClientRect();
      resize = { el, x: e.clientX, y: e.clientY, w: r.width, h: r.height };
      e.preventDefault();
    });
  });

  $$('[data-launch]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      launch(el.dataset.launch, el);
    });
  });

  window.addEventListener('mousemove', (e) => {
    if (drag) {
      let x = e.clientX - drag.wr.left - drag.dx;
      let y = e.clientY - drag.wr.top - drag.dy;
      x = Math.max(-40, Math.min(x, drag.wr.width - 80));
      y = Math.max(0, Math.min(y, drag.wr.height - 40));
      drag.el.style.left = x + 'px';
      drag.el.style.top = y + 'px';
    }
    if (resize) {
      resize.el.style.width = Math.max(280, resize.w + (e.clientX - resize.x)) + 'px';
      resize.el.style.height = Math.max(180, resize.h + (e.clientY - resize.y)) + 'px';
    }
  });
  window.addEventListener('mouseup', () => { drag = null; resize = null; });

  function closeMenus() { appMenu?.classList.remove('is-on'); $('#appBtn')?.classList.remove('is-on'); }
  $('#appBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const on = appMenu.classList.toggle('is-on');
    $('#appBtn').classList.toggle('is-on', on);
  });
  document.addEventListener('click', closeMenus);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeMenus(); splash.classList.remove('is-on'); launching = false; }
  });

  const hashMap = {
    about: 'about', contact: 'contact', projects: 'projects', services: 'about',
    'call-kettle': 'call-kettle', kev: 'kev', 'power-bi': 'power-bi',
    wireshark: 'wireshark', 'phishing-ioc': 'phish', 'agent-lab': 'lab', resume: 'resume'
  };
  function fromHash() {
    const h = (location.hash || '').replace(/^#\/?/, '');
    if (hashMap[h]) launch(hashMap[h]);
  }
  window.addEventListener('hashchange', fromHash);

  /* terminal */
  const out = $('#termOut');
  const input = $('#termInput');
  const hist = [];
  let hi = 0;
  function print(html) {
    if (!out) return;
    out.insertAdjacentHTML('beforeend', html);
    const t = $('.term');
    if (t) t.scrollTop = t.scrollHeight;
  }
  const cmds = {
    help: () => '<span class="dim">whoami  neofetch  ls  cat about.txt  open projects  resume  contact  clear</span>',
    whoami: () => 'sami',
    pwd: () => '/home/sami',
    date: () => new Date().toString(),
    uname: () => 'Linux kali 6.8.0-kali x86_64',
    ls: (a) => (a[0] === 'projects' || a[0] === '~/projects')
      ? 'call-kettle.md  kev.md  power-bi.md  wireshark.md  phishing-ioc.md  lab.md'
      : 'about.txt  contact.txt  projects/  resume.pdf',
    cat: (a) => ({
      'about.txt': 'Sami Ali — cybersecurity, Alexandria VA.\nDHS HS-POWER intern, CBP VAT, Summer 2026.\nSecurity+ · AWS CCP · CBP Full BI.',
      'contact.txt': 'samiali38183@gmail.com · (571) 290-8908'
    }[(a[0] || '').replace(/^~\//, '')] || '<span class="red">No such file</span>'),
    open: (a) => { launch(a[0] || 'projects'); return 'launching…'; },
    projects: () => { launch('projects'); return ''; },
    contact: () => { launch('contact'); return ''; },
    resume: () => { launch('resume'); return ''; },
    clear: () => { out.innerHTML = ''; return ''; },
    neofetch: () => [
      '<span class="red">sami</span>@<span class="red">kali</span>',
      '<span class="dim">-----------</span>',
      '<span class="cyan">Host</span>: Sami Ali · Alexandria, VA',
      '<span class="cyan">Role</span>: cybersecurity · detection / cloud / vuln mgmt',
      '<span class="cyan">Uptime</span>: CBP VAT intern, Summer 2026',
      '<span class="cyan">Packages</span>: Security+, AWS CCP, CBP Full BI',
      '<span class="cyan">GitHub</span>: github.com/samiali38183'
    ].join('\n')
  };
  $('#termForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const raw = input.value.trim();
    input.value = '';
    if (!raw) return;
    hist.push(raw); hi = hist.length;
    const parts = raw.split(/\s+/);
    print('\n<span class="ok">sami@kali</span>:<span class="cyan">~</span>$ ' + raw.replace(/</g, '&lt;') + '\n');
    if (parts[0] === 'echo') { print(parts.slice(1).join(' ') + '\n'); return; }
    const fn = cmds[parts[0]];
    if (!fn) { print('<span class="red">bash: command not found</span>\n'); return; }
    const res = fn(parts.slice(1));
    if (res) print(res + '\n');
  });
  input?.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp' && hist.length) { e.preventDefault(); hi = Math.max(0, hi - 1); input.value = hist[hi] || ''; }
    if (e.key === 'ArrowDown') { e.preventDefault(); hi = Math.min(hist.length, hi + 1); input.value = hist[hi] || ''; }
  });

  $$('a[download]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    if (!/\.pdf($|\?)/i.test(href)) return;
    a.addEventListener('click', async (e) => {
      try {
        e.preventDefault();
        const filename = href.split('/').pop().split('?')[0];
        const res = await fetch(href, { cache: 'no-cache' });
        if (!res.ok) throw 0;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const tmp = document.createElement('a');
        tmp.href = url; tmp.download = filename;
        document.body.appendChild(tmp); tmp.click(); tmp.remove();
        setTimeout(() => URL.revokeObjectURL(url), 800);
      } catch (err) { window.location.href = href; }
    });
  });

  if (location.hash) setTimeout(fromHash, 200);
})();
