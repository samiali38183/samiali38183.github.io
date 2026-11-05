// Terminal portfolio. Vanilla JS, no dependencies. Every fact on this page is from the résumé or the public repos.
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var term = $("term"), form = $("prompt"), input = $("cmd"), ps1 = $("ps1"), chips = $("chips"), screen = $("screen");
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var seen = false;
  try { seen = sessionStorage.getItem("booted") === "1"; } catch (e) {}

  /* ---------------- helpers ---------------- */
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, skipping ? 0 : ms); }); }
  function a(text, href) { return '<a href="' + href + '" target="_blank" rel="noopener">' + text + "</a>"; }
  function cl(text, cmd) { return '<span class="cmdlink" role="button" tabindex="0" data-cmd="' + esc(cmd) + '">' + text + "</span>"; }
  function line(html, cls) {
    var d = document.createElement("div");
    if (cls) d.className = cls;
    d.innerHTML = html === "" ? "&nbsp;" : html;
    term.appendChild(d);
    term.scrollTop = term.scrollHeight;
    return d;
  }
  function pre(html, cls) {
    var d = document.createElement("div");
    d.innerHTML = '<pre class="' + (cls || "") + '">' + html + "</pre>";
    term.appendChild(d);
    term.scrollTop = term.scrollHeight;
  }
  // truncate html to n visible chars, closing open tags (for typing effects)
  function slice(html, n) {
    var out = "", c = 0, i = 0, open = 0;
    while (i < html.length && c < n) {
      if (html[i] === "<") { var j = html.indexOf(">", i), tag = html.slice(i, j + 1); out += tag; if (tag[1] === "/") open--; else if (!/\/>$/.test(tag)) open++; i = j + 1; }
      else if (html[i] === "&") { var k = html.indexOf(";", i); out += html.slice(i, k + 1); c++; i = k + 1; }
      else { out += html[i++]; c++; }
    }
    while (open-- > 0) out += "</span>";
    return out;
  }
  function vlen(html) { var t = document.createElement("div"); t.innerHTML = html; return t.textContent.length; }
  async function typeLine(html, per) {
    if (reduce || skipping) { line(html); return; }
    var d = line(""), n = vlen(html), i = 0;
    d.classList.add("cursor");
    while (i < n && !skipping) { i += 2; d.innerHTML = slice(html, i); term.scrollTop = term.scrollHeight; await sleep(per); }
    d.innerHTML = html; d.classList.remove("cursor");
  }

  /* ---------------- content ---------------- */
  var F = function (html) { return { f: html }; };
  var LINK = function (href, note) { return { href: href, note: note }; };
  var D = function (kids) { return { d: kids }; };

  var H = function (t) { return '<span class="h">' + t + "</span>"; };
  var dim = function (t) { return '<span class="dim">' + t + "</span>"; };

  var tripline = H("# tripline") + "  " + dim("detection quality gate") + "\n" +
    dim("tags: T1548.001 · Sigma · auditd · CloudTrail · GitHub Actions") + "\n\n" +
    "In CI it emulates ATT&amp;CK techniques, replays the telemetry through Sigma rules, scores\ncoverage, and fails the pull request if a rule regresses. No SIEM required.\n\n" +
    '<span class="bad">Finding:</span> SigmaHQ\'s "Setuid and Setgid" rule matched <span class="bad">0 of 36</span> events.\n' +
    "  The rule greps for the literal <code> chmod u+s</code>. The Atomic Red Team test ran <code>chmod u+xs</code>.\n" +
    "  It also misses <code>chmod 4755</code>. Same behavior, no alert. I wrote a replacement rule that\n  matches any setuid/setgid chmod form.\n\n" +
    H("Results") + "\n  AWS CloudTrail   <span class=\"ok\">4/4</span> scenarios pass\n  Linux auditd     <span class=\"ok\">3/3</span> scenarios pass\n  Coverage         <span class=\"warn\">47%</span> weighted (Red Canary 2026 weights); 100% of scenarios that have logs\n  Exports an ATT&amp;CK Navigator layer.\n\n" +
    dim("Not done: the 7 Windows scenarios are pending, which is why overall coverage is 47%.") + "\n\n" +
    a("github.com/samiali38183/tripline", "https://github.com/samiali38183/tripline") + "  ·  try: " + cl("run tripline", "run tripline");

  var sinkline = H("# sinkline") + "  " + dim("taint analysis for Python web apps") + "\n" +
    dim("tags: CWE-89 · CWE-79 · OWASP Top 10 · SARIF · Python ast") + "\n\n" +
    "Interprocedural taint analyzer. Follows user input from request to dangerous sink across\nfunction and file boundaries, maps findings to OWASP and CWE, emits SARIF.\nZero dependencies, built on the standard library's <code>ast</code>.\n\n" +
    H("Benchmark") + dim("  (109 hand-labeled lines, 37 tests; small, and I labeled it, so read the real-app runs too)") + "\n" +
    "  precision 0.983  recall 0.951  F1 <span class=\"ok\">0.967</span>\n  bandit 1.8: precision 0.623  recall 0.541  F1 0.579\n\n" +
    H("Real apps") + "\n  vulpy                  3x CWE-89 across files, 0 in good/\n  Vulnerable-Flask-App   SSTI, SQL injection, XSS, weak MD5\n  dvpwa                  CWE-89, CWE-117\n  microblog (clean)      0 findings\n\n" +
    a("github.com/samiali38183/sinkline", "https://github.com/samiali38183/sinkline") + "  ·  " + a("design notes", "https://github.com/samiali38183/sinkline/blob/main/docs/DESIGN.md") + "  ·  try: " + cl("run sinkline", "run sinkline");

  var kev = H("# kev-risk-prioritization") + "  " + dim("case study + reference implementation") + "\n" +
    dim("tags: CISA KEV · EPSS · CVSS · BOD 26-04") + "\n\n" +
    "CVSS says how bad an exploit <em>could</em> be. KEV says whether anyone <em>is</em> exploiting it.\nA CVSS 8.8 finding that is not in KEV ranks below every KEV match.\n\n" +
    "  average CVSS   KEV 9.53   non-KEV 8.34   " + dim("(similar)") + "\n  average EPSS   KEV 0.935  non-KEV 0.029  " + dim("(very different)") + "\n\n" +
    dim("Synthetic data on purpose: the public repo reproduces the method, not any agency's scan results.") + "\n\n" +
    a("github.com/samiali38183/kev-risk-prioritization", "https://github.com/samiali38183/kev-risk-prioritization") + "  ·  " + a("methodology", "https://github.com/samiali38183/kev-risk-prioritization/blob/main/docs/methodology.md") + "  ·  try: " + cl("run kev", "run kev");

  var vault = H("# cybersecurity-vault") + "\n\n" +
    "Defensive labs: a stdlib phishing-IOC extractor (10 pytest tests) and a Wireshark lab covering\nhandshakes, DNS, TLS SNI and ARP poisoning (ATT&amp;CK T1557.002), with what a defender should\nnotice in each capture.\n\n" +
    a("github.com/samiali38183/cybersecurity-vault", "https://github.com/samiali38183/cybersecurity-vault");

  var callkettle = H("# call-kettle") + "  " + dim("side project: live phone receptionist for home-service shops") + "\n" +
    dim("tags: FastAPI · Twilio · Claude tool-use · Fly.io · SQLite") + "\n\n" +
    "Claude proposes tool calls; code validates every one. Booking rules (hours, slot grid, lead time,\none booking per slot) are enforced in Python, so the model can't book outside hours or claim a\nbooking that didn't happen. Tenant-isolation tests, cost limits, signature-validated webhooks.\n\n" +
    "Built with Hermes Agent and Claude Code working in parallel, gated by 3,400+ tests.\n\n" +
    a("github.com/samiali38183/call-kettle", "https://github.com/samiali38183/call-kettle") + "  ·  " + a("how the agents were used", "https://github.com/samiali38183/call-kettle/blob/main/docs/AGENT_WORK.md");

  var lab = H("# agent-engineering-lab") + "\n\n" +
    "How I run Hermes Agent, Claude Code and Codex in parallel and verify their work: load tests that\ncaught a real concurrency race, tenant isolation, cost limits, no secrets in prompts.\nDeployed on Fly.io with SQLite.\n\n" +
    a("github.com/samiali38183/agent-engineering-lab", "https://github.com/samiali38183/agent-engineering-lab");

  var focuslog = H("# focuslog") + "\n\nFocus-session tracker with a Pomodoro timer, session logging and a weekly dashboard.\n\n" +
    a("github.com/samiali38183/focuslog", "https://github.com/samiali38183/focuslog");

  var dhs = H("# Vulnerability Assessment Analyst Intern") + "\n" +
    dim("DHS HS-POWER · U.S. Customs and Border Protection · Ashburn, VA · May-Aug 2026") + "\n\n" +
    "  * Cut through scan noise: matched enterprise Nessus/Tenable data to the CISA KEV catalog to find\n    what attackers are already exploiting, benchmarked against BOD 26-04.\n" +
    "  * Built a multi-page Power BI dashboard (CVSS, EPSS, remediation age) that made the case that\n    exploitation likelihood, not severity alone, separates real risk.\n" +
    "  * Designed a prioritization methodology ranking findings by KEV status, high-value-asset status,\n    internet exposure, EPSS and CVSS.\n" +
    "  * Translated it for leadership: compliance reporting (NIST CSF, FedRAMP, Zero Trust) and an\n    executive briefing.\n\n" +
    dim("Internal systems and figures are non-public, so nothing here comes from them. The public\nkev-risk-prioritization repo is the same idea on synthetic data.");

  var skills = H("# skills") + "\n\n" +
    "  Vuln management   Nessus/Tenable · CISA KEV · EPSS · CVSS · BOD 26-04 · risk-based prioritization\n" +
    "  Detection         Sigma · MITRE ATT&amp;CK · auditd / CloudTrail telemetry · Wireshark · IOC extraction\n" +
    "  AppSec            taint analysis · OWASP Top 10 / CWE · SARIF · SAST\n" +
    "  Engineering       Python (building fluency) · pytest · Git / GitHub Actions CI · Linux & Windows\n" +
    "  Cloud             AWS fundamentals (Cloud Practitioner)\n" +
    "  Frameworks        NIST CSF · FedRAMP · Zero Trust\n" +
    "  Reporting         Power BI · technical writing · executive briefings";

  var about = H("# Sami Ali") + "\n" +
    "Cybersecurity student at George Mason University (B.S. IT, cybersecurity minor, May 2028).\nAlexandria, VA.\n\n" +
    "I build detection and code-analysis tools, then measure them against real data. One of them found\nthat the stock Sigma rule for setuid abuse matched <span class=\"bad\">0 of 36</span> events. I wrote the replacement.\n\n" +
    "Summer 2026: analyst intern on CBP's Vulnerability Assessment Team (DHS HS-POWER).\n" +
    '<span class="ok">Looking for:</span> security engineering, detection, or vulnerability management internships, Summer 2027.\n\n' +
    "Start here: " + cl("projects", "ls projects") + "  " + cl("work", "cat work/dhs-cbp.md") + "  " + cl("certs", "ls certs") + "  " + cl("contact", "cat contact.txt") + "  " + cl("resume", "open resume.pdf");

  var contact = H("# contact") + "\n\n" +
    "  email     " + a("samiali38183@gmail.com", "mailto:samiali38183@gmail.com") + "\n" +
    "  github    " + a("github.com/samiali38183", "https://github.com/samiali38183") + "\n" +
    "  linkedin  " + a("linkedin.com/in/sami-ali-1a4b89345", "https://www.linkedin.com/in/sami-ali-1a4b89345") + "\n" +
    "  resume    " + cl("resume.pdf", "open resume.pdf");

  var FS = D({
    "about.md": F(about),
    "skills.md": F(skills),
    "contact.txt": F(contact),
    "resume.pdf": LINK("resume.pdf", "Résumé"),
    "projects": D({
      "tripline.md": F(tripline),
      "sinkline.md": F(sinkline),
      "kev-risk-prioritization.md": F(kev),
      "cybersecurity-vault.md": F(vault),
      "other": D({
        "call-kettle.md": F(callkettle),
        "agent-engineering-lab.md": F(lab),
        "focuslog.md": F(focuslog)
      })
    }),
    "work": D({ "dhs-cbp.md": F(dhs) }),
    "education": D({
      "gmu.txt": F("George Mason University\nB.S. Information Technology, minor in Cybersecurity\nExpected May 2028"),
      "nvcc.txt": F("Northern Virginia Community College\nA.S. Information Technology\nMay 2026 · GPA 3.7")
    }),
    "certs": D({
      "security-plus.pdf": LINK("assets/certs/CompTIA-Security-Plus.pdf", "CompTIA Security+"),
      "aws-ccp.pdf": LINK("assets/certs/AWS-Cloud-Practitioner.pdf", "AWS Certified Cloud Practitioner (CLF-C02)"),
      "in-progress.txt": F("In progress:\n  OSCP / OSCP+\n  AWS Certified Security - Specialty (SCS-C03)")
    }),
    ".hidden": D({
      "secret.txt": F(H("# you found it") + "\n\nNobody asked the stock setuid rule about <code>chmod 4755</code> either. Same bit, no alert.\n\n" +
        "tripline's coverage is 47% because the Windows scenarios aren't done yet. They're next.\n\n" + dim("If you read hidden files, we should talk: samiali38183@gmail.com"))
    })
  });

  /* ---------------- shell state ---------------- */
  var cwd = [];            // path segments under ~
  var history = [], hIdx = 0;
  var busy = false, skipping = false;

  function nodeAt(segs) {
    var n = FS;
    for (var i = 0; i < segs.length; i++) { if (!n.d || !n.d[segs[i]]) return null; n = n.d[segs[i]]; }
    return n;
  }
  function resolve(p) {
    var segs = p.charAt(0) === "~" || p.charAt(0) === "/" ? [] : cwd.slice();
    p.replace(/^~\/?/, "").split("/").forEach(function (s) {
      if (s === "" || s === ".") return;
      if (s === "..") { segs.pop(); return; }
      segs.push(s);
    });
    return segs;
  }
  function pwd() { return "/home/guest" + (cwd.length ? "/" + cwd.join("/") : ""); }
  function ps1Text() { return '<span class="ps-u">guest@sami-ali</span>:<span class="ps-p">~' + (cwd.length ? "/" + cwd.join("/") : "") + "</span>$ "; }
  function setPrompt() { ps1.innerHTML = ps1Text(); }
  function names(n, all) { return Object.keys(n.d).filter(function (k) { return all || k[0] !== "."; }); }

  var COMMANDS = {
    help: function () {
      var rows = [
        ["ls [-a] [dir]", "list files (-a shows hidden)"], ["cd <dir>", "change directory"], ["cat <file>", "read a file"], ["pwd", "print working directory"],
        ["tree", "show the whole file system"], ["find <name>", "search for files"], ["run <name>", "replay a result: tripline · sinkline · kev"],
        ["open <file>", "open a PDF or link"], ["whoami", "who's asking"], ["neofetch", "the short version"], ["history", "commands you've run"],
        ["theme <name>", "dark · amber · paper"], ["clear", "clear the screen (Ctrl+L)"], ["exit", "log out (and reboot)"]
      ];
      line(H("Commands"));
      rows.forEach(function (r) { line("  " + cl(r[0].split(" ")[0], r[0].split(" ")[0]) + r[0].slice(r[0].split(" ")[0].length) + " ".repeat(Math.max(1, 16 - r[0].length)) + dim(r[1])); });
      line("");
      line(dim("Shortcuts: Tab completes · ↑/↓ history · click any underlined word. Hidden files exist. ls -a"));
    },
    ls: function (args) {
      var all = false, target = cwd.slice();
      args.forEach(function (x) { if (x[0] === "-") { if (x.indexOf("a") > 0) all = true; } else target = resolve(x); });
      var n = nodeAt(target);
      if (!n) return line("ls: cannot access: No such file or directory", "bad");
      if (!n.d) return line(target[target.length - 1]);
      var base = target.join("/");
      var parts = names(n, all).map(function (k) {
        var isDir = !!n.d[k].d, p = (base ? base + "/" : "") + k;
        return isDir ? cl('<span class="hl b">' + k + "/</span>", "cd " + p) : cl(k, "cat " + p);
      });
      line(parts.join("   "));
    },
    cd: function (args) {
      var t = args[0] ? resolve(args[0]) : [];
      var n = nodeAt(t);
      if (!n) return line("cd: " + esc(args[0]) + ": No such file or directory", "bad");
      if (!n.d) return line("cd: " + esc(args[0]) + ": Not a directory", "bad");
      cwd = t; setPrompt();
    },
    pwd: function () { line(pwd()); },
    cat: function (args) {
      if (!args.length) return line("cat: missing file. Try: cat about.md");
      args.forEach(function (x) {
        var n = nodeAt(resolve(x));
        if (!n) return line("cat: " + esc(x) + ": No such file or directory", "bad");
        if (n.d) return line("cat: " + esc(x) + ": Is a directory", "bad");
        if (n.href) return COMMANDS.open([x]);
        pre(n.f);
        line("");
      });
    },
    open: function (args) {
      var n = args[0] && nodeAt(resolve(args[0]));
      if (!n || !n.href) return line("open: " + esc(args[0] || "") + ": nothing to open. Try: open resume.pdf", "bad");
      line("opening " + esc(n.note || args[0]) + " ... " + a("click if it didn't open", n.href));
      window.open(n.href, "_blank", "noopener");
    },
    tree: function () {
      var out = [];
      (function walk(n, prefix) {
        var ks = names(n, true);
        ks.forEach(function (k, i) {
          var last = i === ks.length - 1;
          out.push(prefix + (last ? "└── " : "├── ") + (n.d[k].d ? '<span class="hl b">' + k + "/</span>" : k));
          if (n.d[k].d) walk(n.d[k], prefix + (last ? "    " : "│   "));
        });
      })(FS, "");
      pre(".\n" + out.join("\n"));
    },
    find: function (args) {
      var pat = args.filter(function (x) { return x !== "-name"; })[0];
      if (!pat) return line("usage: find <name>");
      pat = pat.toLowerCase().replace(/\*/g, "");
      var hits = [];
      (function walk(n, path) {
        Object.keys(n.d).forEach(function (k) {
          var p = path + "/" + k;
          if (k.toLowerCase().indexOf(pat) >= 0) hits.push(p);
          if (n.d[k].d) walk(n.d[k], p);
        });
      })(FS, ".");
      if (!hits.length) return line("(no matches)", "dim");
      hits.forEach(function (h) { var rel = h.slice(2); var n = nodeAt(rel.split("/")); line("  " + (n.d ? cl(h, "cd " + rel) : cl(h, "cat " + rel))); });
    },
    whoami: function () { line("guest   " + dim("(that's you. I'm Sami Ali: ") + cl("cat about.md", "cat about.md") + dim(")")); },
    neofetch: function () {
      pre('<span class="hl b">guest</span>@<span class="hl b">sami-ali</span>\n----------------\n' +
        '<span class="hl">Name</span>       Sami Ali\n<span class="hl">School</span>     George Mason University, B.S. IT (cyber minor), May 2028\n' +
        '<span class="hl">Prior</span>      NVCC A.S. IT, May 2026, GPA 3.7\n<span class="hl">Certs</span>      Security+, AWS Cloud Practitioner\n' +
        '<span class="hl">Intern</span>     DHS HS-POWER · CBP Vulnerability Assessment Team (summer 2026)\n<span class="hl">Focus</span>      detection engineering · vulnerability management · appsec\n' +
        '<span class="hl">Studying</span>   OSCP · AWS Security Specialty\n<span class="hl">Shell</span>      this page: vanilla JS, 0 dependencies');
      line("");
    },
    history: function () { history.forEach(function (h, i) { line(("   " + (i + 1)).slice(-4) + "  " + esc(h)); }); },
    clear: function () { term.innerHTML = ""; },
    theme: function (args) {
      var t = (args[0] || "").toLowerCase();
      if (["dark", "amber", "paper"].indexOf(t) < 0) return line("usage: theme dark | amber | paper");
      screen.setAttribute("data-theme", t);
      try { localStorage.setItem("theme", t); } catch (e) {}
      line("theme: " + t, "dim");
    },
    sudo: function () { line("guest is not in the sudoers file. This incident will be reported.", "bad"); },
    rm: function () { line("rm: permission denied. (This is a portfolio, not a lab VM.)", "bad"); },
    exit: async function () {
      line("logout"); await sleep(500); line("Connection to sami-ali closed.", "dim"); await sleep(900);
      cwd = []; form.hidden = true; chips.hidden = true; term.innerHTML = ""; boot(true);
    },
    run: async function (args) {
      var w = args[0];
      if (w === "tripline") {
        busy = true;
        var rows = [
          '<span class="dim">tripline · detection quality gate · technique T1548.001 (setuid / setgid)</span>',
          "$ emulate  <span class=\"ok\">chmod u+xs /tmp/probe</span>", "  captured 36 auditd events",
          '$ replay   SigmaHQ "Setuid and Setgid" over those events', '  matched  <span class="bad">0 / 36   MISS</span>',
          '<span class="dim">why   the rule greps for the literal " chmod u+s". The test ran "u+xs". It also misses "chmod 4755".</span>',
          '<span class="dim">fix   replacement rule: any setuid/setgid chmod form.</span>',
          '<span class="ok">That was a real result from tripline.</span>'
        ];
        for (var i = 0; i < rows.length; i++) { await typeLine(rows[i], 8); await sleep(250); }
        busy = false;
      } else if (w === "sinkline") {
        var m = [["precision", 0.983, 0.623], ["recall   ", 0.951, 0.541], ["F1       ", 0.967, 0.579]];
        line(dim("sinkline vs bandit 1.8 · 109 hand-labeled lines (small, self-labeled)"));
        line('<span class="ok">■</span> sinkline   <span class="dim">■ bandit</span>');
        m.forEach(function (r) {
          var w1 = Math.round(r[1] * 40), w2 = Math.round(r[2] * 40);
          line(r[0] + "  " + '<span class="ok">' + "█".repeat(w1) + "</span> " + r[1].toFixed(3));
          line("           " + '<span class="dim">' + "█".repeat(w2) + "</span> " + r[2].toFixed(3));
        });
      } else if (w === "kev") {
        line(dim("kev-risk-prioritization · synthetic sample"));
        line("avg CVSS  KEV " + "█".repeat(Math.round(9.53 * 4)) + " 9.53");
        line("          non " + '<span class="dim">' + "█".repeat(Math.round(8.34 * 4)) + "</span> 8.34");
        line("avg EPSS  KEV " + '<span class="ok">' + "█".repeat(Math.round(0.935 * 40)) + "</span> 0.935");
        line("          non " + '<span class="dim">' + "█".repeat(Math.max(1, Math.round(0.029 * 40))) + "</span> 0.029");
        line('<span class="warn">Similar severity, very different exploitation likelihood.</span>');
      } else {
        line("usage: run tripline | sinkline | kev   (or try: " + cl("run tripline", "run tripline") + ")");
      }
    }
  };
  COMMANDS["ll"] = function (a2) { COMMANDS.ls(["-a"].concat(a2)); };
  COMMANDS["dir"] = COMMANDS.ls;
  COMMANDS["logout"] = COMMANDS.exit;
  COMMANDS["projects"] = function () { COMMANDS.ls(["projects"]); };
  COMMANDS["resume"] = function () { COMMANDS.open(["resume.pdf"]); };

  async function exec(raw, echo) {
    var cmdline = raw.trim();
    if (echo) line(ps1Text() + esc(raw));
    if (!cmdline) return;
    if (history[history.length - 1] !== cmdline) history.push(cmdline);
    hIdx = history.length;
    var parts = cmdline.split(/\s+/), c = parts[0], args = parts.slice(1);
    if (COMMANDS[c]) { busy = true; try { await COMMANDS[c](args); } finally { busy = false; } }
    else line("bash: " + esc(c) + ": command not found. Try " + cl("help", "help") + ".", "bad");
    term.scrollTop = term.scrollHeight;
  }

  /* ---------------- input ---------------- */
  form.addEventListener("submit", function (e) { e.preventDefault(); if (busy) return; var v = input.value; input.value = ""; exec(v, true); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowUp") { e.preventDefault(); if (hIdx > 0) input.value = history[--hIdx]; }
    else if (e.key === "ArrowDown") { e.preventDefault(); hIdx = Math.min(history.length, hIdx + 1); input.value = history[hIdx] || ""; }
    else if (e.key === "l" && e.ctrlKey) { e.preventDefault(); COMMANDS.clear(); }
    else if (e.key === "c" && e.ctrlKey) { e.preventDefault(); line(ps1Text() + esc(input.value) + "^C"); input.value = ""; }
    else if (e.key === "Tab") { e.preventDefault(); complete(); }
  });
  function complete() {
    var v = input.value, toks = v.split(/\s+/), last = toks[toks.length - 1], cands;
    if (toks.length === 1) cands = Object.keys(COMMANDS);
    else {
      var slash = last.lastIndexOf("/"), dirPart = slash >= 0 ? last.slice(0, slash + 1) : "", n = nodeAt(resolve(dirPart || "."));
      cands = n && n.d ? Object.keys(n.d).map(function (k) { return dirPart + k + (n.d[k].d ? "/" : ""); }) : [];
    }
    var m = cands.filter(function (c) { return c.indexOf(last) === 0; });
    if (m.length === 1) { toks[toks.length - 1] = m[0]; input.value = toks.join(" ") + (m[0].slice(-1) === "/" ? "" : " "); }
    else if (m.length > 1) {
      var p = m[0]; m.forEach(function (c) { while (c.indexOf(p) !== 0) p = p.slice(0, -1); });
      toks[toks.length - 1] = p; input.value = toks.join(" ");
      line(ps1Text() + esc(v)); line(m.map(esc).join("   "), "dim");
    }
  }
  function runLink(el) { if (busy) return; var c = el.getAttribute("data-cmd"); exec(c, true); input.focus({ preventScroll: true }); }
  term.addEventListener("click", function (e) { var t = e.target.closest(".cmdlink"); if (t) { e.preventDefault(); runLink(t); } else if (!window.getSelection().toString()) input.focus({ preventScroll: true }); });
  term.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("cmdlink")) { e.preventDefault(); runLink(e.target); } });

  /* ---------------- boot + login ---------------- */
  var BOOT = [
    ['[    0.000000] <span class="ok">Linux</span> sami-ali 2028.05-gmu #1 SMP (B.S. Information Technology, cybersecurity minor)', 0],
    ["[    0.004112] location: Alexandria, VA", 60],
    ['[    0.011380] cert: CompTIA Security+ .......................... <span class="ok">[ OK ]</span>', 90],
    ['[    0.012044] cert: AWS Certified Cloud Practitioner (CLF-C02) .... <span class="ok">[ OK ]</span>', 70],
    ['[    0.020917] intern: DHS HS-POWER / CBP Vulnerability Assessment Team, May-Aug 2026 .... <span class="ok">[ DONE ]</span>', 90],
    ['[    0.031205] sinkline: F1 0.967 vs bandit 0.579 (109 hand-labeled lines) ........... <span class="ok">[ OK ]</span>', 120],
    ["[    0.033871] tripline: replaying SigmaHQ 'Setuid and Setgid' over 36 auditd events", 150],
    ['[    0.034502] tripline: matched 0/36 ................................... <span class="bad">[ FAIL ]</span>', 260],
    ['[    0.034503] tripline: cause: rule greps " chmod u+s"; the test ran "u+xs"', 90],
    ['[    0.036010] tripline: replacement rule loaded ........................ <span class="ok">[ OK ]</span>', 200],
    ['[    0.041660] oscp: <span class="warn">in progress</span>   aws scs-c03: <span class="warn">in progress</span>', 110],
    ["", 120]
  ];

  async function boot(replay) {
    skipping = false;
    var wasSeen = seen && !replay;
    var onSkip = function (e) { if (e.type === "keydown" && e.key !== "Escape" && e.key !== "Enter" && e.key !== " ") return; skipping = true; };
    document.addEventListener("keydown", onSkip); document.addEventListener("pointerdown", onSkip);
    var fast = reduce || wasSeen;
    if (fast) skipping = true;
    if (!fast) line(dim("press any key to skip"));
    for (var i = 0; i < BOOT.length; i++) { await sleep(BOOT[i][1]); line(BOOT[i][0]); }
    await sleep(300);
    var host = line("sami-ali login: "), user = "guest";
    if (!skipping) { var d = host; for (var k = 1; k <= user.length; k++) { d.innerHTML = "sami-ali login: " + user.slice(0, k); await sleep(110); } }
    host.innerHTML = "sami-ali login: " + user;
    await sleep(250);
    line(dim("Last login: " + new Date().toDateString() + " from your browser"));
    line("");
    skipping = false;
    document.removeEventListener("keydown", onSkip); document.removeEventListener("pointerdown", onSkip);
    try { sessionStorage.setItem("booted", "1"); seen = true; } catch (e) {}

    pre(
      " ___   _   __  __ ___     _   _    ___ \n/ __| /_\\ |  \\/  |_ _|   /_\\ | |  |_ _|\n\\__ \\/ _ \\| |\\/| || |   / _ \\| |__ | | \n|___/_/ \\_\\_|  |_|___| /_/ \\_\\____|___|",
      "banner"
    );
    line(dim("security engineering · detection · vulnerability management"));
    line("");
    form.hidden = false; chips.hidden = false; setPrompt();
  }

  // The first screen: typed command + output, so the page has content immediately.
  async function firstScreen() {
    line(ps1Text() + "cat about.md");
    COMMANDS.cat(["about.md"]);
  }

  function makeChips() {
    chips.innerHTML = "";
    ["help", "cat about.md", "ls projects", "run tripline", "cat work/dhs-cbp.md", "ls certs", "cat contact.txt", "open resume.pdf"].forEach(function (c) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = c;
      b.addEventListener("click", function () { if (!busy) { exec(c, true); input.focus({ preventScroll: true }); } });
      chips.appendChild(b);
    });
  }

  // legacy deep links from the old multi-page site (#work, #kev, ...)
  var HASH = { work: "ls projects", experience: "cat work/dhs-cbp.md", kev: "cat projects/kev-risk-prioritization.md", also: "cat projects/other/call-kettle.md", contact: "cat contact.txt", about: "cat about.md" };

  async function start() {
    try { var t = localStorage.getItem("theme"); if (t) screen.setAttribute("data-theme", t); } catch (e) {}
    makeChips();
    var clock = $("clock");
    (function tick() { var d = new Date(); clock.textContent = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); setTimeout(tick, 20000); })();
    await boot(false);
    var h = (location.hash || "").slice(1);
    if (HASH[h] && h !== "about") { await exec(HASH[h], true); } else { await firstScreen(); }
    line("");
    line(dim("Type " ) + cl("help", "help") + dim(", press Tab, or click the buttons below. ") + dim("Hidden files exist: ls -a"));
    input.focus({ preventScroll: true });
  }
  start();
})();
