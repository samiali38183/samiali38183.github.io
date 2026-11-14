/* Global enhancements: theme toggle and copy buttons. The site works without this file.
   Strip entrance and the page transition are CSS only. Budget: 3 KB gzipped. */
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('theme');

  function stored() { try { return localStorage.getItem('theme'); } catch (e) { return null; } }
  function store(v) { try { localStorage.setItem('theme', v); } catch (e) { /* storage blocked: keep the choice for this page only */ } }
  function systemDark() { return !!(window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches); }
  function current() { return root.getAttribute('data-theme') || (systemDark() ? 'dark' : 'light'); }

  var saved = stored();
  if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved);

  if (btn) {
    btn.hidden = false;
    btn.setAttribute('aria-pressed', String(current() === 'dark'));
    btn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      store(next);
      btn.setAttribute('aria-pressed', String(next === 'dark'));
    });
  }

  /* A link to a section that is folded (#method, #trace) opens it. Without this script the fold stays closed and the heading is still shown. */
  function openFold() {
    var el = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    var d = el && (el.closest('details') || el.querySelector('details.fold'));
    if (d) { d.open = true; el.scrollIntoView(); }
  }
  openFold();
  addEventListener('hashchange', openFold);

  if (navigator.clipboard) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-copy-email]'), function (b) {
      b.hidden = false;
      b.addEventListener('click', function () {
        navigator.clipboard.writeText(b.dataset.copyEmail).then(function () {
          b.textContent = 'Copied';
          setTimeout(function () { b.textContent = 'Copy'; }, 1500);
        }, function () { b.textContent = 'Press Ctrl+C'; });
      });
    });
  }

  if (navigator.clipboard) {
    Array.prototype.forEach.call(document.querySelectorAll('pre[data-copy]'), function (pre) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'copy';
      b.textContent = 'Copy';
      b.setAttribute('aria-label', 'Copy to clipboard' + (pre.dataset.label ? ': ' + pre.dataset.label : ''));
      b.addEventListener('click', function () {
        var code = pre.querySelector('code');
        navigator.clipboard.writeText((code || pre).textContent).then(function () {
          b.textContent = 'Copied';
          setTimeout(function () { b.textContent = 'Copy'; }, 1500);
        }, function () { b.textContent = 'Press Ctrl+C'; });
      });
      pre.appendChild(b);
    });
  }
})();
