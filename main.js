/* Portfolio interactions:
   - Mobile sidebar drawer
   - Light/dark theme toggle (persisted)
   - Accent color picker (persisted)
   - Reveal-on-scroll for .reveal
   - Animated skill bars when in view
   - Back-to-top button
   - Projects filter (on projects.html)
*/
(function(){
  'use strict';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

  // ---- Mobile drawer ----
  const sidebar = $('#sidebar');
  const menuToggle = $('#menuToggle');
  if (menuToggle && sidebar){
    menuToggle.addEventListener('click', () => {
      const open = sidebar.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(open));
    });
    // Close on nav click (mobile)
    sidebar.querySelectorAll('.sidebar__link').forEach(a => {
      a.addEventListener('click', () => sidebar.classList.remove('is-open'));
    });
    // Close on outside click (mobile)
    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)){
        sidebar.classList.remove('is-open');
      }
    });
  }

  // ---- Theme toggle (light/dark) ----
  const themeToggle = $('#themeToggle');
  const applyTheme = (t) => {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('theme', t); } catch(e){}
  };
  const savedTheme = (() => { try { return localStorage.getItem('theme'); } catch(e){ return null; } })();
  if (savedTheme === 'light' || savedTheme === 'dark'){
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
  if (themeToggle){
    themeToggle.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      applyTheme(cur === 'dark' ? 'light' : 'dark');
    });
  }

  // ---- Accent color picker ----
  const COLORS = {
    blue:   { accent:'#1E88E5', hi:'#64B5F6' },
    teal:   { accent:'#14B8A6', hi:'#5EEAD4' },
    violet: { accent:'#8B5CF6', hi:'#C4B5FD' },
    rose:   { accent:'#F43F5E', hi:'#FDA4AF' },
    amber:  { accent:'#F59E0B', hi:'#FCD34D' },
  };
  const paletteToggle = $('#paletteToggle');
  const colorPicker = $('#colorPicker');
  const applyColor = (name) => {
    const c = COLORS[name]; if (!c) return;
    document.documentElement.style.setProperty('--accent', c.accent);
    document.documentElement.style.setProperty('--accent-hi', c.hi);
    $$('.swatch').forEach(s => s.classList.toggle('is-active', s.dataset.color === name));
    try { localStorage.setItem('accent', name); } catch(e){}
  };
  const savedColor = (() => { try { return localStorage.getItem('accent'); } catch(e){ return null; } })();
  if (savedColor && COLORS[savedColor]) applyColor(savedColor);

  if (paletteToggle && colorPicker){
    paletteToggle.addEventListener('click', () => colorPicker.classList.toggle('is-open'));
    document.addEventListener('click', (e) => {
      if (!colorPicker.contains(e.target) && !paletteToggle.contains(e.target)){
        colorPicker.classList.remove('is-open');
      }
    });
    $$('.swatch', colorPicker).forEach(s => {
      const activate = () => applyColor(s.dataset.color);
      s.addEventListener('click', activate);
      s.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); activate(); } });
    });
  }

  // ---- Reveal on scroll ----
  const revealEls = $$('.reveal');
  if (revealEls.length && 'IntersectionObserver' in window && !reduce){
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting){
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });
    revealEls.forEach(el => io.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('is-in'));
  }

  // ---- Skill bar animation ----
  const skillEls = $$('.skill');
  if (skillEls.length){
    const setBars = (el) => {
      const fill = el.querySelector('.skill__fill');
      const pct  = parseFloat(el.dataset.pct || '0');
      if (fill) fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
    };
    if ('IntersectionObserver' in window && !reduce){
      const sio = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting){ setBars(entry.target); sio.unobserve(entry.target); }
        });
      }, { threshold: 0.2 });
      skillEls.forEach(el => sio.observe(el));
    } else {
      skillEls.forEach(setBars);
    }
  }

  // ---- Back to top ----
  const toTop = $('#toTop');
  if (toTop){
    const onScroll = () => toTop.classList.toggle('is-visible', window.scrollY > 400);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' }));
  }

  // ---- Letter-by-letter flow for the hero role accent ("Cybersecurity Engineer") ----
  const roleAccent = $('.hero__role .accent');
  if (roleAccent && !reduce){
    const text = roleAccent.textContent;
    roleAccent.innerHTML = [...text].map((ch, i) => {
      const delay = (0.50 + i * 0.045).toFixed(3);
      if (ch === ' ') return '<span class="letter-space" aria-hidden="true"></span>';
      return `<span class="letter" style="animation-delay:${delay}s">${ch}</span>`;
    }).join('');
    // Keep the accessible text unchanged
    roleAccent.setAttribute('aria-label', text);
  }

  // ---- Word-by-word flow-in for the hero lead paragraph ----
  const lead = $('.hero__lead');
  if (lead && !reduce){
    const text = lead.textContent.trim();
    const words = text.split(/\s+/);
    lead.innerHTML = words.map((w, i) =>
      `<span class="flow-word" style="animation-delay:${(0.45 + i * 0.035).toFixed(3)}s">${w}</span>`
    ).join(' ');
  }

  // ---- Force download on PDF links (browsers preview PDFs otherwise) ----
  $$('a[download]').forEach(a => {
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
        // fallback: let the browser handle it
        window.location.href = href;
      }
    });
  });

  // ---- Contact form success banner (after Formsubmit redirect) ----
  if (window.location.search.includes('sent=1')){
    const note = $('#sentNote');
    if (note){
      note.style.display = 'block';
      note.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    }
    // Clean the URL so refresh doesn't re-show
    if (history.replaceState) history.replaceState(null, '', window.location.pathname);
  }

  // ---- Projects filter ----
  const filterBtns = $$('.filter__btn');
  const cards = $$('#proj-grid .card');
  if (filterBtns.length && cards.length){
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => { b.classList.remove('is-active'); b.setAttribute('aria-selected', 'false'); });
        btn.classList.add('is-active'); btn.setAttribute('aria-selected', 'true');
        const f = btn.dataset.filter;
        cards.forEach(c => {
          const show = f === 'all' || (c.dataset.tags || '').split(/\s+/).includes(f);
          c.style.display = show ? '' : 'none';
        });
      });
    });
  }
})();
