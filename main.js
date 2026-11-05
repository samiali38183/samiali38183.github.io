// Intro: a replay of a real result from the tripline project (see README in that repo).
// Skipped for reduced-motion users and for repeat visits in the same tab session; always skippable.
(function () {
  "use strict";
  var gate = document.getElementById("gate");
  var log = document.getElementById("gate-log");
  var skip = document.getElementById("gate-skip");
  var replay = document.getElementById("replay");
  if (!gate || !log) return;

  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var seen = false;
  try { seen = sessionStorage.getItem("gate-seen") === "1"; } catch (e) {}

  // [html, delay-before-ms, per-char-ms]
  var script = [
    ['<span class="dim">tripline · detection quality gate · technique T1548.001 (setuid / setgid)</span>', 0, 8],
    ["", 250, 0],
    ['$ emulate  <span class="ok">chmod u+xs /tmp/probe</span>', 300, 24],
    ['  captured 36 auditd events', 450, 10],
    ['$ replay   SigmaHQ "Setuid and Setgid" over those events', 500, 14],
    ['  matched  <span class="bad">0 / 36   MISS</span>', 900, 30],
    ["", 400, 0],
    ['<span class="dim">why   the rule greps for the literal " chmod u+s".</span>', 400, 8],
    ['<span class="dim">      the test ran "u+xs". it also misses "chmod 4755".</span>', 100, 8],
    ['<span class="dim">fix   replacement rule: any setuid/setgid chmod form.</span>', 400, 8],
    ["", 500, 0],
    ['<span class="ok">That was a real result from my project tripline, not a demo.</span>', 500, 14],
    ['<span class="ok">Sami Ali. Details below.</span>', 200, 14]
  ];

  var timers = [];
  var done = false;
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

  function finish() {
    if (done) return;
    done = true;
    timers.forEach(clearTimeout);
    try { sessionStorage.setItem("gate-seen", "1"); } catch (e) {}
    gate.classList.add("out");
    document.documentElement.style.overflow = "";
    setTimeout(function () { gate.hidden = true; gate.classList.remove("out"); }, 650);
    document.removeEventListener("keydown", onKey);
  }
  function onKey(e) { if (e.key === "Escape" || e.key === "Enter" || e.key === " ") { e.preventDefault(); finish(); } }

  function run() {
    done = false;
    log.innerHTML = "";
    gate.hidden = false;
    gate.classList.remove("out");
    document.documentElement.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);
    skip.focus();

    var t = 0;
    var lines = script.map(function () {
      var d = document.createElement("div");
      log.appendChild(d);
      return d;
    });
    script.forEach(function (row, i) {
      var html = row[0], pre = row[1], per = row[2];
      t += pre;
      var start = t;
      later(function () {
        lines.forEach(function (l) { l.classList.remove("cur"); });
        lines[i].classList.add("cur");
        if (!html) { lines[i].innerHTML = "&nbsp;"; return; }
        // type the visible text while keeping markup intact
        var tmp = document.createElement("div");
        tmp.innerHTML = html;
        var text = tmp.textContent.length;
        var n = 0;
        (function tick() {
          if (done) return;
          n += 2;
          lines[i].innerHTML = sliceHTML(html, n);
          if (n < text) later(tick, per);
        })();
      }, start);
      t += html ? Math.ceil(html.length / 2) * per : 0;
    });
    later(finish, t + 1500);
  }

  // return `html` truncated to `n` visible characters, closing open tags
  function sliceHTML(html, n) {
    var out = "", count = 0, open = [], i = 0;
    while (i < html.length && count < n) {
      if (html[i] === "<") {
        var j = html.indexOf(">", i);
        var tag = html.slice(i, j + 1);
        out += tag;
        if (tag[1] === "/") open.pop(); else open.push(tag);
        i = j + 1;
      } else if (html[i] === "&") {
        var k = html.indexOf(";", i);
        out += html.slice(i, k + 1); count++; i = k + 1;
      } else { out += html[i]; count++; i++; }
    }
    open.forEach(function () { out += "</span>"; });
    return out;
  }

  skip.addEventListener("click", finish);
  gate.addEventListener("click", function (e) { if (e.target === gate) finish(); });
  if (replay) replay.addEventListener("click", function (e) { e.preventDefault(); window.scrollTo(0, 0); run(); });

  if (!reduce && !seen) run();
})();
