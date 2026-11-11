/* Optional enhancements: theme toggle and copy buttons. The site works without this file. */
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('theme');
  function stored() { try { return localStorage.getItem('theme'); } catch (e) { return null; } }
  function store(v) { try { localStorage.setItem('theme', v); } catch (e) { /* ignore */ } }
  function systemDark() { return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches; }
  var saved = stored();
  if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved);
  if (btn) {
    btn.hidden = false;
    var sync = function () {
      var cur = root.getAttribute('data-theme') || (systemDark() ? 'dark' : 'light');
      btn.textContent = cur === 'dark' ? 'Light theme' : 'Dark theme';
    };
    sync();
    btn.addEventListener('click', function () {
      var cur = root.getAttribute('data-theme') || (systemDark() ? 'dark' : 'light');
      var next = cur === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      store(next);
      sync();
    });
  }
  var pres = document.querySelectorAll('pre[data-copy]');
  Array.prototype.forEach.call(pres, function (pre) {
    if (!navigator.clipboard) return;
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'copy';
    b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy code to clipboard');
    b.addEventListener('click', function () {
      navigator.clipboard.writeText(pre.innerText.replace(/Copy$/, '').trim()).then(function () {
        b.textContent = 'Copied';
        setTimeout(function () { b.textContent = 'Copy'; }, 1500);
      });
    });
    pre.appendChild(b);
  });
})();
