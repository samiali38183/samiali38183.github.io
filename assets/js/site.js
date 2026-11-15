/* Optional enhancements: copy buttons and folded-section anchors. The site works without this file. */
(function () {
  /* A link to a section that is folded (#method, #trace) opens it. Without this script the fold stays closed and the heading is still shown. */
  function openFold() {
    var el = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    var d = el && (el.closest('details') || el.querySelector('details.fold'));
    if (d) { d.open = true; el.scrollIntoView(); }
  }
  openFold();
  addEventListener('hashchange', openFold);

  /* Copy text. Uses the Clipboard API where it is allowed, otherwise a temporary textarea and execCommand. Resolves true on success. */
  function copyText(text, anchor) {
    function legacy() {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.opacity = '0';
      (anchor && anchor.parentNode || document.body).appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.parentNode.removeChild(ta);
      if (anchor) anchor.focus();
      return ok;
    }
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacy(); });
    }
    return Promise.resolve(legacy());
  }

  function selectNode(node) {
    var r = document.createRange();
    r.selectNodeContents(node);
    var s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-copy-email]'), function (b) {
    var wrap = b.closest('.email-copy');
    var status = wrap && wrap.querySelector('.copy-status');
    var label = b.textContent;
    b.hidden = false;
    b.addEventListener('click', function () {
      copyText(b.dataset.copyEmail, b).then(function (ok) {
        if (ok) {
          b.textContent = 'Copied';
          if (status) status.textContent = 'Copied to clipboard';
        } else {
          var a = wrap && wrap.querySelector('.email');
          if (a) selectNode(a);
          b.textContent = 'Press Ctrl+C';
          if (status) status.textContent = 'Address selected';
        }
        setTimeout(function () { b.textContent = label; if (status) status.textContent = ''; }, 2000);
      });
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('pre[data-copy]'), function (pre) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'copy';
    b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy to clipboard' + (pre.dataset.label ? ': ' + pre.dataset.label : ''));
    b.addEventListener('click', function () {
      var code = pre.querySelector('code');
      copyText((code || pre).textContent, b).then(function (ok) {
        b.textContent = ok ? 'Copied' : 'Press Ctrl+C';
        setTimeout(function () { b.textContent = 'Copy'; }, 1500);
      });
    });
    pre.appendChild(b);
  });
})();
