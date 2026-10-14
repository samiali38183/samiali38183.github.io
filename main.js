/* Kali-style window manager + terminal for the one-page workstation */
(function () {
  'use strict';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const machine = $('#machine');
  const workspace = $('#workspace');
  const boot = $('#boot');
  const appMenu = $('#appMenu');
  const ctx = $('#ctx');
  const clockEl = $('#clock');
  const tasks = $('#tasks');
  const selbox = $('#selbox');
  let z = 20;
  let drag = null;
  let resize = null;
  let machineDrag = null;

  function clock() {
    const d = new Date();
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const m = String(d.getMinutes()).padStart(2, '0');
    if (clockEl) clockEl.textContent = days[d.getDay()] + ' ' + d.getHours() + ':' + m;
  }
  clock();
  setInterval(clock, 10000);

  function finishBoot() {
    if (!boot || boot.classList.contains('is-gone')) return;
    boot.classList.add('is-gone');
    setTimeout(() => { if (boot && boot.parentNode) boot.remove(); }, 500);
    openWin('readme');
    openWin('term');
  }
  function runBoot() {
    const lines = boot ? $$('.boot__line', boot) : [];
    if (reduce || !boot) { finishBoot(); return; }
    lines.forEach((el, i) => setTimeout(() => el.classList.add('on'), 90 * i));
    setTimeout(finishBoot, 90 * lines.length + 350);
  }
  $('#skipBoot')?.addEventListener('click', (e) => { e.stopPropagation(); finishBoot(); });
  boot?.addEventListener('click', finishBoot);

  function winEl(id) { return document.querySelector('.win[data-id="' + id + '"]'); }

  function focusWin(id) {
    const el = winEl(id);
    if (!el) return;
    z += 1;
    el.style.zIndex = String(z);
    $$('.win').forEach((w) => w.classList.toggle('is-focus', w === el));
    $$('.task').forEach((t) => t.classList.toggle('is-active', t.dataset.id === id));
  }

  function renderTasks() {
    if (!tasks) return;
    tasks.innerHTML = '';
    $$('.win.is-open').forEach((w) => {
      if (w.classList.contains('is-min')) return;
      const b = document.createElement('button');
      b.className = 'task' + (w.classList.contains('is-focus') ? ' is-active' : '');
      b.dataset.id = w.dataset.id;
      b.textContent = w.dataset.title;
      b.addEventListener('click', () => {
        if (w.classList.contains('is-min')) {
          w.classList.remove('is-min');
          w.classList.add('is-open');
        }
        focusWin(w.dataset.id);
      });
      tasks.appendChild(b);
    });
  }

  function openWin(id) {
    const el = winEl(id);
    if (!el) return;
    el.classList.add('is-open');
    el.classList.remove('is-min');
    if (!el.dataset.placed) {
      const n = $$('.win.is-open').length;
      el.style.left = (36 + (n * 26) % 180) + 'px';
      el.style.top = (28 + (n * 22) % 120) + 'px';
      if (!el.style.width) el.style.width = el.dataset.w || '520px';
      if (!el.style.height) el.style.height = el.dataset.h || '360px';
      el.dataset.placed = '1';
    }
    focusWin(id);
    renderTasks();
    if (id === 'term') setTimeout(() => $('#termInput')?.focus(), 50);
  }

  function closeWin(id) {
    const el = winEl(id);
    if (!el) return;
    el.classList.remove('is-open', 'is-min', 'is-max', 'is-focus');
    renderTasks();
  }

  function minWin(id) {
    const el = winEl(id);
    if (!el) return;
    el.classList.add('is-min');
    el.classList.remove('is-focus');
    renderTasks();
  }

  function maxWin(id) {
    const el = winEl(id);
    if (!el) return;
    el.classList.toggle('is-max');
    focusWin(id);
  }

  $$('.win').forEach((el) => {
    el.addEventListener('mousedown', () => focusWin(el.dataset.id));
    el.querySelector('[data-act="x"]')?.addEventListener('click', (e) => { e.stopPropagation(); closeWin(el.dataset.id); });
    el.querySelector('[data-act="m"]')?.addEventListener('click', (e) => { e.stopPropagation(); minWin(el.dataset.id); });
    el.querySelector('[data-act="M"]')?.addEventListener('click', (e) => { e.stopPropagation(); maxWin(el.dataset.id); });
    el.querySelector('.titlebar')?.addEventListener('dblclick', () => maxWin(el.dataset.id));
    const bar = el.querySelector('.titlebar');
    bar?.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      if (e.target.closest('.ctrl')) return;
      if (el.classList.contains('is-max')) return;
      const r = el.getBoundingClientRect();
      const wr = workspace.getBoundingClientRect();
      drag = { el, dx: e.clientX - r.left, dy: e.clientY - r.top, wr };
      e.preventDefault();
    });
    el.querySelector('.rsz')?.addEventListener('mousedown', (e) => {
      e.stopPropagation();
      const r = el.getBoundingClientRect();
      resize = { el, x: e.clientX, y: e.clientY, w: r.width, h: r.height };
      e.preventDefault();
    });
  });

  $$('.icon').forEach((ic) => {
    ic.addEventListener('click', (e) => {
      e.stopPropagation();
      $$('.icon').forEach((x) => x.classList.remove('is-sel'));
      ic.classList.add('is-sel');
      const t = ic.dataset.open;
      if (t === 'resume-file') {
        const a = document.createElement('a');
        a.href = 'resume.pdf'; a.download = 'Sami-Ali-Resume.pdf'; a.click();
        return;
      }
      openWin(t);
    });
  });

  workspace?.addEventListener('mousedown', (e) => {
    if (e.target !== workspace && !e.target.classList.contains('wallpaper') && e.target.id !== 'mark') return;
    $$('.icon').forEach((x) => x.classList.remove('is-sel'));
    closeMenus();
    if (!selbox) return;
    const wr = workspace.getBoundingClientRect();
    selbox.style.display = 'block';
    selbox.dataset.x = String(e.clientX - wr.left);
    selbox.dataset.y = String(e.clientY - wr.top);
    selbox.style.left = selbox.dataset.x + 'px';
    selbox.style.top = selbox.dataset.y + 'px';
    selbox.style.width = '0';
    selbox.style.height = '0';
  });

  window.addEventListener('mousemove', (e) => {
    if (drag) {
      const wr = drag.wr;
      let x = e.clientX - wr.left - drag.dx;
      let y = e.clientY - wr.top - drag.dy;
      x = Math.max(-40, Math.min(x, wr.width - 80));
      y = Math.max(0, Math.min(y, wr.height - 40));
      drag.el.style.left = x + 'px';
      drag.el.style.top = y + 'px';
    }
    if (resize) {
      resize.el.style.width = Math.max(280, resize.w + (e.clientX - resize.x)) + 'px';
      resize.el.style.height = Math.max(180, resize.h + (e.clientY - resize.y)) + 'px';
    }
    if (machineDrag && machine && !machine.classList.contains('is-fs')) {
      machine.style.left = (e.clientX - machineDrag.dx) + 'px';
      machine.style.top = (e.clientY - machineDrag.dy) + 'px';
      machine.style.transform = 'none';
    }
    if (selbox && selbox.style.display === 'block' && selbox.dataset.x) {
      const wr = workspace.getBoundingClientRect();
      const x0 = +selbox.dataset.x, y0 = +selbox.dataset.y;
      const x1 = e.clientX - wr.left, y1 = e.clientY - wr.top;
      selbox.style.left = Math.min(x0, x1) + 'px';
      selbox.style.top = Math.min(y0, y1) + 'px';
      selbox.style.width = Math.abs(x1 - x0) + 'px';
      selbox.style.height = Math.abs(y1 - y0) + 'px';
    }
  });
  window.addEventListener('mouseup', () => {
    drag = null; resize = null; machineDrag = null;
    if (selbox) {
      selbox.style.display = 'none';
      delete selbox.dataset.x;
    }
  });

  $('#lidGrab')?.addEventListener('mousedown', (e) => {
    if (!machine || machine.classList.contains('is-fs')) return;
    if (e.target.closest('.screen')) return;
    const r = machine.getBoundingClientRect();
    machineDrag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    e.preventDefault();
  });

  $('#fsBtn')?.addEventListener('click', () => {
    machine.classList.toggle('is-fs');
    $('#fsBtn').textContent = machine.classList.contains('is-fs') ? 'Undock' : 'Fullscreen';
  });

  function closeMenus() {
    appMenu?.classList.remove('is-open');
    ctx?.classList.remove('is-open');
    $('#appBtn')?.classList.remove('is-open');
  }
  $('#appBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = appMenu.classList.toggle('is-open');
    $('#appBtn').classList.toggle('is-open', open);
    const r = $('#appBtn').getBoundingClientRect();
    const wr = $('.os').getBoundingClientRect();
    appMenu.style.left = (r.left - wr.left) + 'px';
    appMenu.style.top = (r.bottom - wr.top) + 'px';
  });
  workspace?.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const wr = $('.os').getBoundingClientRect();
    ctx.style.left = (e.clientX - wr.left) + 'px';
    ctx.style.top = (e.clientY - wr.top) + 'px';
    ctx.classList.add('is-open');
  });
  document.addEventListener('click', closeMenus);

  $$('[data-open]').forEach((b) => {
    if (b.classList.contains('icon')) return;
    b.addEventListener('click', () => { closeMenus(); openWin(b.dataset.open); });
  });

  const hashMap = {
    about: 'about', contact: 'contact', projects: 'projects', services: 'about',
    'call-kettle': 'call-kettle', kev: 'kev', 'power-bi': 'power-bi',
    wireshark: 'wireshark', 'phishing-ioc': 'phish', 'agent-lab': 'lab'
  };
  function fromHash() {
    const h = (location.hash || '').replace(/^#\/?/, '');
    if (hashMap[h]) openWin(hashMap[h]);
  }
  window.addEventListener('hashchange', fromHash);

  const out = $('#termOut');
  const input = $('#termInput');
  const hist = [];
  let hi = 0;

  function print(html) {
    if (!out) return;
    out.insertAdjacentHTML('beforeend', html);
    const term = $('#termBody');
    if (term) term.scrollTop = term.scrollHeight;
  }

  const files = {
    'about.txt': 'Sami Ali — cybersecurity. Alexandria, VA.\nDHS HS-POWER intern, CBP Vulnerability Assessment Team, Summer 2026.\nSecurity+ · AWS CCP · CBP Full BI (active).\nAiming at detection, cloud security, and security engineering internships for 2027.',
    'contact.txt': 'email: samiali38183@gmail.com\nphone: (571) 290-8908\nlinkedin: linkedin.com/in/sami-ali-1a4b89345\ngithub: github.com/samiali38183',
    'projects/call-kettle.md': 'Call Kettle — AI voice receptionist\nFastAPI + Twilio + Claude Haiku tool-use.\nBuilt/iterated with Claude Code and Hermes Agent.\nPublic snapshot: github.com/samiali38183/call-kettle\nLive: callkettle.com',
    'projects/kev.md': 'KEV / BOD 26-04 prioritization — CBP intern work, sanitized case study.\nRank findings by confirmed exploitation + EPSS, not raw CVSS.',
    'projects/lab.md': 'Agent Engineering Lab — orchestrating coding agents (Hermes, Claude Code, Codex) behind pytest gates.'
  };

  const cmds = {
    help() {
      return '<span class="dim">whoami, neofetch, ls, cat, open, projects, resume, contact, clear, date, uname, help</span>';
    },
    whoami() { return 'sami'; },
    date() { return new Date().toString(); },
    uname() { return 'Linux kali 6.8.0-kali x86_64 GNU/Linux'; },
    pwd() { return '/home/sami'; },
    ls(args) {
      if (args[0] === 'projects' || args[0] === '~/projects') {
        return 'call-kettle.md  kev.md  power-bi.md  wireshark.md  phishing-ioc.md  lab.md';
      }
      return 'about.txt  contact.txt  projects/  resume.pdf';
    },
    cat(args) {
      const f = args[0] || '';
      const key = f.replace(/^~\//, '').replace(/^\.\//, '');
      return files[key] ? files[key] : '<span class="red">cat: ' + f + ': No such file</span>';
    },
    open(args) {
      const map = { about: 'about', contact: 'contact', projects: 'projects', term: 'term', terminal: 'term', resume: 'resume', lab: 'lab', 'call-kettle': 'call-kettle', kev: 'kev' };
      const id = map[(args[0] || '').toLowerCase()];
      if (!id) return '<span class="red">open: unknown window</span>';
      openWin(id);
      return 'opened ' + id;
    },
    projects() { openWin('projects'); return 'opening ~/projects'; },
    contact() { openWin('contact'); return 'opening contact'; },
    resume() {
      const a = document.createElement('a');
      a.href = 'resume.pdf'; a.download = 'Sami-Ali-Resume.pdf'; a.click();
      return 'downloading resume.pdf';
    },
    clear() { if (out) out.innerHTML = ''; return ''; },
    neofetch() {
      return [
        '<span class="red">sami</span>@<span class="red">kali</span>',
        '<span class="dim">-----------</span>',
        '<span class="cyan">OS</span>: Kali GNU/Linux (portfolio session)',
        '<span class="cyan">Host</span>: Sami Ali · Alexandria, VA',
        '<span class="cyan">Kernel</span>: defensive security + LLM tool-use',
        '<span class="cyan">Uptime</span>: HS-POWER intern, CBP VAT, Summer 2026',
        '<span class="cyan">Packages</span>: Security+, AWS CCP, CBP Full BI',
        '<span class="cyan">Shell</span>: bash 5.2',
        '<span class="cyan">WM</span>: this page — drag the machine, drag the windows',
        '<span class="cyan">GitHub</span>: github.com/samiali38183'
      ].join('\n');
    }
  };

  function run(line) {
    const raw = line.trim();
    if (!raw) return;
    hist.push(raw); hi = hist.length;
    const parts = raw.split(/\s+/);
    const cmd = parts[0];
    const args = parts.slice(1);
    print('\n<span class="ok">sami@kali</span>:<span class="cyan">~</span>$ ' + raw.replace(/</g, '&lt;') + '\n');
    if (cmd === 'echo') { print(args.join(' ') + '\n'); return; }
    const fn = cmds[cmd];
    if (!fn) { print('<span class="red">bash: ' + cmd + ': command not found</span>\n'); return; }
    const res = fn(args);
    if (res) print(res + '\n');
  }

  $('#termForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const v = input.value;
    input.value = '';
    run(v);
  });
  input?.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!hist.length) return;
      hi = Math.max(0, hi - 1);
      input.value = hist[hi] || '';
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      hi = Math.min(hist.length, hi + 1);
      input.value = hist[hi] || '';
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenus();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openWin('term');
    }
  });

  $$('a[download]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    if (!/\.pdf($|\?)/i.test(href)) return;
    a.addEventListener('click', async (e) => {
      try {
        e.preventDefault();
        const filename = href.split('/').pop().split('?')[0];
        const res = await fetch(href, { cache: 'no-cache' });
        if (!res.ok) throw new Error('fetch failed');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const tmp = document.createElement('a');
        tmp.href = url; tmp.download = filename;
        document.body.appendChild(tmp); tmp.click(); tmp.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (err) {
        window.location.href = href;
      }
    });
  });

  runBoot();
  setTimeout(fromHash, reduce ? 0 : 400);
})();
