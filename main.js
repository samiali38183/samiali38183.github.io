(function () {
  "use strict";

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const out = $("#out");
  const input = $("#cmd");
  const form = $("#form");
  const win = $("#win");
  const suggest = $("#suggest");
  const hits = $("#hits");
  const clockEl = $("#clock");
  const themes = ["night", "phosphor", "paper"];
  const NAMES = [
    "whoami", "now", "intern", "projects", "stack", "certs",
    "resume", "contact", "github", "help", "clear", "ls", "cat", "theme", "date"
  ];
  const DESC = {
    whoami: "Who Sami is",
    now: "What he’s doing this year",
    intern: "CBP VAT internship",
    projects: "Selected work",
    stack: "Tools and agents",
    certs: "Certifications",
    resume: "PDF resume",
    contact: "Email, phone, LinkedIn",
    github: "GitHub profile",
    help: "Show commands",
    clear: "Clear the screen",
    ls: "List files",
    cat: "Read a file",
    theme: "Cycle terminal theme",
    date: "Local time"
  };
  const FILES = {
    "about.txt": "whoami",
    "now.txt": "now",
    "projects.md": "projects",
    "stack.md": "stack",
    "contact.txt": "contact",
    "resume.pdf": "resume"
  };

  const hist = [];
  let hi = 0;
  let themeIdx = 0;
  let booting = false;

  function setVh() {
    const h = (window.visualViewport && window.visualViewport.height) || window.innerHeight;
    document.documentElement.style.setProperty("--vh", h + "px");
  }
  setVh();
  window.visualViewport?.addEventListener("resize", setVh);
  window.addEventListener("resize", setVh);

  function tickClock() {
    clockEl.textContent = new Date().toLocaleTimeString("en-GB", { hour12: false });
  }
  tickClock();
  setInterval(tickClock, 1000);

  try {
    const saved = localStorage.getItem("sami-theme");
    if (saved && themes.includes(saved)) {
      themeIdx = themes.indexOf(saved);
      applyTheme(saved, true);
    }
  } catch (e) {}

  function applyTheme(name, silent) {
    if (name === "night") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", name);
    const meta = document.querySelector('meta[name="theme-color"]');
    const colors = { night: "#07090d", phosphor: "#041108", paper: "#ece7dc" };
    if (meta) meta.setAttribute("content", colors[name] || colors.night);
    try { localStorage.setItem("sami-theme", name); } catch (e) {}
    if (!silent) $("#statusMid").textContent = "theme: " + name;
  }

  function sleep(ms) {
    if (reduce) return Promise.resolve();
    return new Promise((r) => setTimeout(r, ms));
  }

  function html(s) {
    const d = document.createElement("div");
    d.innerHTML = s;
    out.appendChild(d);
    out.scrollTop = out.scrollHeight;
    return d;
  }

  function bootLine(text, cls) {
    html('<div class="line boot ' + (cls || "") + '">' + text + "</div>");
  }

  const BANNER =
    '   _____           _ \n' +
    '  / ____|         (_)\n' +
    ' | (___   __ _ _ __ _ \n' +
    '  \\___ \\ / _` | \'_ ` _ \\\n' +
    '  ____) | (_| | | | | | |\n' +
    ' |_____/ \\__,_|_| |_| |_|  ali\n';

  function helpHtml() {
    const groups = {
      About: ["whoami", "now", "intern", "certs"],
      Work: ["projects", "stack", "resume"],
      Connect: ["contact", "github"],
      Terminal: ["theme", "clear", "ls", "cat", "help"]
    };
    let t = '<div class="mb"><div class="bold">Available commands</div><div class="mut">---</div>';
    Object.entries(groups).forEach(([g, list]) => {
      t += '<div class="bold mt">' + g + "</div>";
      list.forEach((c) => {
        t += '<div class="ml"><span class="acc">' + c + "</span> — " + DESC[c] + "</div>";
      });
    });
    t += '<div class="mut mb" style="margin-top:10px">Tab autocompletes. Shift+Tab cycles themes. Shortcuts sit under the window.</div></div>';
    return t;
  }

  const CMDS = {
    help: () => helpHtml(),
    whoami: () =>
      '<div class="mb">' +
      '<div class="acc bold">Sami Ali</div>' +
      "<div>Cybersecurity student, Alexandria, VA.</div>" +
      "<div>Summer 2026 intern on CBP’s Vulnerability Assessment Team (DHS HS-POWER).</div>" +
      "<div>Targeting detection, cloud security, and security-engineering internships for 2027.</div>" +
      '<div class="grid">' +
      "<div><span class=\"mut\">location</span>  Alexandria, VA</div>" +
      "<div><span class=\"mut\">clearance</span>  CBP Full BI — active</div>" +
      "<div><span class=\"mut\">available</span>  Summer 2027</div>" +
      "<div><span class=\"mut\">learning</span>  HTB CPTS · OSCP</div>" +
      "</div>" +
      "<div><span class=\"mut\">edu</span>  B.S. IT, George Mason (2026–2028), cybersecurity minor</div>" +
      "<div><span class=\"mut\">edu</span>  A.S. IT, NOVA (2024–2026), GPA 3.7</div>" +
      "</div>",
    now: () =>
      '<div class="mb"><div class="bold">Now</div>' +
      "<div>• Wrapping CBP VAT intern work: risk-based vuln prioritization, dashboard, briefing</div>" +
      "<div>• Building with coding agents (Hermes, Claude Code, Codex) against real repos + pytest</div>" +
      "<div>• Studying toward CPTS / OSCP</div>" +
      "<div>• Looking at 2027 internships in detection / cloud / AppSec, DC–NoVA</div></div>",
    intern: () =>
      '<div class="mb"><div class="bold">CBP · Vulnerability Assessment Team</div>' +
      "<div>DHS HS-POWER · May–Aug 2026 · Ashburn, VA</div>" +
      "<div>Risk-based ranking on agency scan data. Confirmed exploitation and EPSS ahead of raw CVSS. Executive view so “critical” is not treated as “exploited.”</div></div>",
    projects: () =>
      '<div class="mb"><div class="bold">Selected work</div>' +
      '<div class="ml"><span class="acc">agent-lab</span> — teams of coding agents on real repos; pytest is the gate</div>' +
      '<div class="ml"><span class="acc">call-kettle</span> — AI voice receptionist. Claude Haiku tool-use, FastAPI, Twilio. Built with Claude Code + Hermes. <a href="https://github.com/samiali38183/call-kettle" target="_blank" rel="noopener">code</a></div>' +
      '<div class="ml"><span class="acc">kev / bod 26-04</span> — public write-up of CBP-style KEV/EPSS prioritization</div>' +
      '<div class="ml"><span class="acc">power-bi kev</span> — executive dashboard: similar CVSS, different EPSS</div>' +
      '<div class="ml"><span class="acc">wireshark-lab</span> — packet write-ups from the pcap, not the dashboard</div>' +
      '<div class="ml"><span class="acc">phishing-ioc</span> — Python CLI: extract / normalize indicators</div>' +
      '<div class="mut">cat projects.md  ·  ls</div></div>',
    stack: () =>
      '<div class="mb"><div class="bold">Stack</div>' +
      "<div>Python · FastAPI · pytest · Twilio · YAML tenants</div>" +
      "<div>Claude Haiku (tool-use runtime) · Claude Code · Hermes Agent · Codex</div>" +
      "<div>Power BI · Wireshark · GitHub · Vercel / Fly</div></div>",
    certs: () =>
      '<div class="mb"><div class="bold">Certifications</div>' +
      '<div>CompTIA Security+ · <a href="assets/certs/CompTIA-Security-Plus.pdf">PDF</a></div>' +
      '<div>AWS Cloud Practitioner (CLF-C02) · <a href="assets/certs/AWS-Cloud-Practitioner.pdf">PDF</a></div>' +
      "<div class=\"mut\">in progress: CPTS, OSCP</div></div>",
    resume: () =>
      '<div class="mb">Resume (PDF) — <a href="resume.pdf" download>download</a> · <a href="resume.pdf" target="_blank" rel="noopener">open</a></div>',
    contact: () =>
      '<div class="mb"><div class="bold">Connect</div>' +
      '<div><a href="mailto:samiali38183@gmail.com">samiali38183@gmail.com</a></div>' +
      '<div><a href="tel:+15712908908">(571) 290-8908</a></div>' +
      '<div><a href="https://www.linkedin.com/in/sami-ali-1a4b89345" target="_blank" rel="noopener">LinkedIn</a> · <a href="https://github.com/samiali38183" target="_blank" rel="noopener">GitHub</a></div>' +
      "<div class=\"mut\">Internships / security-engineering · DC / NoVA</div></div>",
    github: () =>
      '<div class="mb"><a href="https://github.com/samiali38183" target="_blank" rel="noopener">github.com/samiali38183</a></div>',
    ls: () =>
      '<div class="mb"><span class="acc">about.txt</span>  <span class="acc">now.txt</span>  <span class="acc">projects.md</span>  <span class="acc">stack.md</span>  <span class="acc">contact.txt</span>  <span class="acc">resume.pdf</span></div>',
    date: () => '<div class="mb">' + new Date().toString() + "</div>",
    theme: () => {
      themeIdx = (themeIdx + 1) % themes.length;
      applyTheme(themes[themeIdx]);
      return '<div class="mb">theme → <span class="acc">' + themes[themeIdx] + "</span></div>";
    },
    clear: () => {
      out.innerHTML = "";
      return "";
    }
  };

  CMDS.cat = (args) => {
    const f = (args[0] || "").replace(/^~\//, "");
    if (!f) return '<div class="err mb">usage: cat &lt;file&gt;</div>';
    if (FILES[f]) return CMDS[FILES[f]]();
    return '<div class="err mb">cat: ' + f.replace(/</g, "&lt;") + ": no such file</div>";
  };

  function echoPrompt(raw) {
    html(
      '<div class="entry"><div class="cmdrow"><span class="ok">sami</span><span class="acc">@nova</span> <span class="mut">~</span> % ' +
        raw.replace(/</g, "&lt;") +
        "</div></div>"
    );
  }

  function run(raw, fromChip) {
    const line = (raw || "").trim();
    if (!line) return;
    if (!fromChip) {
      hist.push(line);
      hi = hist.length;
    }
    echoPrompt(line);
    const parts = line.split(/\s+/);
    const name = parts[0].toLowerCase();
    const args = parts.slice(1);
    hideSuggest();
    if (name === "echo") {
      html('<div class="mb">' + args.join(" ").replace(/</g, "&lt;") + "</div>");
      return;
    }
    const fn = CMDS[name];
    if (!fn) {
      html('<div class="err mb">zsh: command not found: ' + name.replace(/</g, "&lt;") + " — try <span class=\"acc\">help</span></div>");
      return;
    }
    const res = fn(args);
    if (res) html(res);
    location.hash = name === "help" ? "" : name;
  }

  function matches(q) {
    if (!q) return [];
    return NAMES.filter((n) => n.startsWith(q.toLowerCase()));
  }

  function showSuggest(list) {
    if (!list.length) {
      hideSuggest();
      return;
    }
    hits.innerHTML = "";
    list.forEach((n) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = n;
      b.addEventListener("click", () => {
        input.value = n;
        hideSuggest();
        input.focus();
      });
      hits.appendChild(b);
    });
    suggest.classList.add("on");
  }

  function hideSuggest() {
    suggest.classList.remove("on");
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = input.value;
    input.value = "";
    run(v);
  });

  input.addEventListener("input", () => {
    const q = input.value.trim();
    showSuggest(matches(q));
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const q = input.value.trim();
      const m = matches(q);
      if (m.length === 1) {
        input.value = m[0];
        hideSuggest();
      } else if (m.length > 1) showSuggest(m);
    }
    if (e.key === "Tab" && e.shiftKey) {
      e.preventDefault();
      themeIdx = (themeIdx + 1) % themes.length;
      applyTheme(themes[themeIdx]);
    }
    if (e.key === "ArrowUp" && hist.length) {
      e.preventDefault();
      hi = Math.max(0, hi - 1);
      input.value = hist[hi] || "";
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      hi = Math.min(hist.length, hi + 1);
      input.value = hist[hi] || "";
    }
    if (e.key === "Escape") hideSuggest();
  });

  document.querySelectorAll("[data-run]").forEach((el) => {
    el.addEventListener("click", () => run(el.dataset.run, true));
  });
  $("#btnHelp").addEventListener("click", () => run("help", true));
  $("#btnClose").addEventListener("click", () => boot(true));
  $("#btnMin").addEventListener("click", () => win.classList.toggle("is-min"));
  $("#btnMax").addEventListener("click", () => win.classList.toggle("is-max"));
  $("#winTitle").addEventListener("dblclick", () => win.classList.toggle("is-max"));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") win.classList.remove("is-min");
    const tag = (e.target && e.target.tagName) || "";
    if (tag !== "INPUT" && tag !== "TEXTAREA" && e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
      input.focus();
    }
  });

  const HASH = {
    about: "whoami",
    whoami: "whoami",
    now: "now",
    intern: "intern",
    projects: "projects",
    stack: "stack",
    certs: "certs",
    resume: "resume",
    contact: "contact",
    github: "github",
    services: "whoami",
    "call-kettle": "projects",
    kev: "projects"
  };

  async function boot(reset) {
    if (booting) return;
    booting = true;
    win.classList.remove("is-min");
    out.innerHTML = "";
    const d = new Date();
    const stamp = d.toLocaleDateString() + " " + d.toLocaleTimeString("en-GB", { hour12: false });
    bootLine(stamp);
    await sleep(350);
    bootLine('Initializing terminal... <span class="ok">done</span>');
    await sleep(420);
    bootLine('Loading modules... <span class="ok">done</span>');
    await sleep(420);
    bootLine('Connecting to samiali38183.github.io ... <span class="ok">done</span>');
    await sleep(380);
    html('<div class="banner">' + BANNER.replace(/</g, "&lt;") + "</div>");
    html('<div class="mut mb">Type <span class="acc">help</span> or tap a shortcut below.</div>');
    booting = false;
    input.focus();
    if (!reset) {
      const h = (location.hash || "").replace(/^#\/?/, "");
      if (HASH[h]) setTimeout(() => run(HASH[h], true), 80);
    }
  }

  window.addEventListener("hashchange", () => {
    const h = (location.hash || "").replace(/^#\/?/, "");
    if (HASH[h]) run(HASH[h], true);
  });

  boot(false);
})();
