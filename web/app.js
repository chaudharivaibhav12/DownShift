/* Downshift console. No build step: plain JS against /api/*. Every number shown comes from the API. */
(() => {
  "use strict";

  const PATH = {
    cheap: { c: "#00A35C", label: "CHEAP", tier: "cheap", name: "cheap model" },
    mid: { c: "#D89B00", label: "MID", tier: "mid", name: "mid model" },
    learn: { c: "#3B5BDB", label: "LEARN", tier: "frontier", name: "frontier model, learned" },
    frontier: { c: "#151719", label: "FRONTIER", tier: "frontier", name: "frontier model" },
  };
  const KIND = {
    search: { k: "SKILL SEARCH", c: "#8A9099" },
    cheap: { k: "CHEAP MODEL", c: "#00A35C" },
    mid: { k: "MID MODEL", c: "#D89B00" },
    frontier: { k: "FRONTIER MODEL", c: "#3B5BDB" },
    db: { k: "ATLAS", c: "#00684A" },
    check: { k: "CHECK", c: "#8A9099" },
    gate: { k: "PROMOTION GATE", c: "#3B5BDB" },
  };

  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const oid = (x) => (x && typeof x === "object" ? x.$oid : x);
  const date = (x) => new Date(x && typeof x === "object" ? x.$date : x);
  const hms = (x) => date(x).toLocaleTimeString([], { hour12: false });
  const usd = (n, digits) => {
    if (n == null) return "—";
    if (digits == null) digits = n === 0 ? 2 : n < 0.01 ? 4 : n < 1 ? 3 : 2;
    return "$" + n.toFixed(digits);
  };
  const secs = (ms) => (ms >= 1000 ? (ms / 1000).toFixed(2) + " s" : Math.round(ms) + " ms");
  const num = (v) => (typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 })) : v);

  let S = null;                 // last /api/state
  let selected = null;          // selected answer id
  let follow = true;            // follow the newest answer
  let pending = null;           // question in flight
  let renderedKey = null;
  let repairSel = null;
  let seenEvents = new Set();
  let firstFeed = true;
  const full = new Map();       // answer id -> full answer (with rows)

  // ------------------------------------------------------------------ data
  async function api(path, opts = {}) {
    const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || r.statusText);
    return body;
  }

  let refreshTimer = null;
  function refreshSoon() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, 120);
  }
  async function refresh() {
    try {
      S = await api("/api/state");
      render();
    } catch (e) {
      $("live").classList.add("off");
    }
  }

  function connect() {
    const es = new EventSource("/api/stream");
    es.onopen = () => $("live").classList.remove("off");
    es.onmessage = refreshSoon;
    es.onerror = () => $("live").classList.add("off");
  }

  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => (t.hidden = true), 3200);
  }

  // ------------------------------------------------------------------ routing
  function view() {
    const v = (location.hash || "#live").slice(1);
    return ["live", "repairs", "skills"].includes(v) ? v : "live";
  }
  function showView() {
    const v = view();
    for (const name of ["live", "repairs", "skills"]) $("view-" + name).hidden = name !== v;
    document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("on", a.dataset.view === v));
    render();
  }
  window.addEventListener("hashchange", showView);

  // ------------------------------------------------------------------ header
  function renderHeader() {
    const st = S.stats;
    const job = S.job;
    $("stats").innerHTML =
      `<span><b>${st.answers}</b> answers</span><span><b>${st.skillsLive}</b> skills live</span>` +
      (st.flagged ? `<span style="color:#8A6200"><b style="color:#8A6200">${st.flagged}</b> flagged</span>` : "") +
      `<span><b>${usd(st.spent, 3)}</b> spent</span>`;
    $("demoTag").hidden = !S.demo;
    $("resetBtn").hidden = !S.demo;
    const busy = !!job.name;
    $("replayBtn").disabled = busy;
    $("replayBtn").textContent = job.name === "replay" ? `Replaying ${job.done}/${job.total}…` : "Replay 30 questions";
    $("schemaBtn").disabled = busy;
    $("schemaBtn").textContent = job.name === "schema-change" ? "Repairing…" : "Simulate schema change";
    $("askBtn").disabled = busy || !!pending;
    const r = S.repair;
    $("repairBadge").hidden = !(r && r.stage !== "done");
  }

  // ------------------------------------------------------------------ live: questions
  function renderQuestions() {
    const list = S.answers;
    if (follow && list.length) selected = oid(list[0]._id);
    let html = "";
    if (pending) {
      html += `<div class="q pending on" style="--c:#8A9099"><span class="t">${esc(pending)}</span><span class="m"><span class="dot"></span>running…</span></div>`;
    }
    for (const a of list) {
      const id = oid(a._id);
      const p = PATH[a.path] || { c: "#D94A4A", label: "FAILED" };
      const on = !pending && id === selected;
      html += `<button type="button" class="q${on ? " on" : ""}" data-id="${id}" style="--c:${p.c}">
        <span class="t">${esc(a.question)}</span>
        <span class="m"><span class="dot"></span>${p.label} · ${usd(a.cost)} · ${secs(a.ms)}${a.source === "replay" ? " · replay" : ""}</span></button>`;
    }
    if (!html) html = `<div class="empty">No answers yet. Ask a question below, or press <b>Replay 30 questions</b> to watch Downshift learn and then shift to the cheap model.</div>`;
    $("qlist").innerHTML = html;
  }
  $("qlist").addEventListener("click", (e) => {
    const b = e.target.closest(".q[data-id]");
    if (!b) return;
    selected = b.dataset.id;
    follow = S.answers.length && oid(S.answers[0]._id) === selected;
    render();
  });

  function renderChips() {
    const chips = (S.suggestions || []).slice(0, 5);
    const key = chips.join("|");
    if ($("chips").dataset.key === key) return;
    $("chips").dataset.key = key;
    $("chips").innerHTML = chips.map((q) => `<button type="button" class="chip" title="${esc(q)}">${esc(q)}</button>`).join("");
  }
  $("chips").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (!b) return;
    $("askInput").value = b.title;
    ask(b.title);
  });

  async function ask(q) {
    q = (q || "").trim();
    if (!q || pending) return;
    $("askErr").hidden = true;
    pending = q;
    follow = true;
    render();
    try {
      const a = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: q }) });
      full.set(oid(a._id), a);
      selected = oid(a._id);
      $("askInput").value = "";
    } catch (e) {
      $("askErr").textContent = e.message;
      $("askErr").hidden = false;
    } finally {
      pending = null;
      await refresh();
    }
  }
  $("askForm").addEventListener("submit", (e) => {
    e.preventDefault();
    ask($("askInput").value);
  });

  // ------------------------------------------------------------------ live: center + inspector
  async function selectedAnswer() {
    if (!selected) return null;
    if (full.has(selected)) return full.get(selected);
    try {
      const a = await api("/api/answers/" + selected);
      full.set(selected, a);
      return a;
    } catch {
      return null;
    }
  }

  function triedTiers(a) {
    const hit = PATH[a.path] ? PATH[a.path].tier : null;
    const t = new Set();
    for (const s of a.steps || []) if ((s.kind === "cheap" || s.kind === "mid") && s.kind !== hit) t.add(s.kind);
    return t;
  }

  function renderPath(a) {
    const stops = document.querySelectorAll("#rail .stop");
    const track = $("track");
    stops.forEach((s) => {
      s.classList.remove("hit");
      s.querySelector(".d").className = "d";
      s.style.removeProperty("--c");
    });
    if (!a || !PATH[a.path]) {
      track.hidden = true;
      $("pathNote").textContent = a ? "no answer" : "ask a question to start";
      return;
    }
    const p = PATH[a.path];
    const tried = triedTiers(a);
    const pos = { frontier: 0, mid: 1, cheap: 2 };
    stops.forEach((s) => {
      const tier = s.dataset.tier;
      const d = s.querySelector(".d");
      if (tier === p.tier) {
        s.classList.add("hit");
        s.style.setProperty("--c", p.c);
        d.classList.add("hit");
      } else if (tried.has(tier)) d.classList.add("tried");
    });
    let right = pos[p.tier];
    for (const t of tried) right = Math.max(right, pos[t]);
    if (right > pos[p.tier]) {
      track.hidden = false;
      track.style.setProperty("--c", p.c);
      track.style.left = ["60px", "50%", "calc(100% - 60px)"][pos[p.tier]];
      track.style.right = ["calc(100% - 60px)", "50%", "60px"][right];
    } else track.hidden = true;
    const model = (a.steps || []).filter((s) => s.model && s.ok).map((s) => s.model).pop();
    $("pathNote").textContent = `${p.name}${model ? " (" + model + ")" : ""} · ${secs(a.ms)} · ${usd(a.cost)}`;
  }

  function nodeDetail(s) {
    const i = s.name.indexOf(" · ");
    return i >= 0 ? s.name.slice(i + 3) : s.name;
  }

  function renderFlow(a) {
    if (!a) {
      $("flow").innerHTML = `<div class="empty" style="padding:4px 0">The steps each answer takes appear here: which model, which skill, what ran on Atlas.</div>`;
      return;
    }
    const steps = a.steps || [];
    const parts = steps.map((s, i) => {
      const k = KIND[s.kind] || { k: s.kind.toUpperCase(), c: "#8A9099" };
      const c = s.kind === "frontier" && a.path === "frontier" ? "#151719" : k.c;
      const sub = [s.ms ? secs(s.ms) : null, s.cost ? usd(s.cost) : null, s.detail && s.kind !== "db" ? s.detail : null].filter(Boolean).join(" · ");
      return `<div class="node-wrap" style="animation-delay:${i * 60}ms">
        <div class="node${s.ok ? "" : " bad"}" style="--c:${c}"><span class="k">${esc(k.k)}${s.ok ? "" : " · FAILED"}</span><span class="v">${esc(nodeDetail(s))}</span>${sub ? `<span class="s">${esc(sub)}</span>` : ""}</div>
        <span class="arrow" style="--c:${s.ok ? c : "#D94A4A"}"></span></div>`;
    });
    const p = PATH[a.path];
    parts.push(`<div class="node-wrap" style="animation-delay:${steps.length * 60}ms"><div class="node" style="--c:${p ? p.c : "#D94A4A"}"><span class="k">ANSWER</span><span class="v">${a.rowCount} row${a.rowCount === 1 ? "" : "s"}</span></div></div>`);
    $("flow").innerHTML = parts.join("");
  }

  function renderAtlas(a) {
    const steps = a ? a.steps || [] : [];
    const kinds = new Set(steps.map((s) => s.kind));
    const c = S.counts || {};
    const colls = [
      { n: "sales", note: `${num(c.sales ?? 0)} docs`, hot: kinds.has("db") },
      { n: "skills", note: `${S.stats.skillsLive} live · ${c.skills ?? 0} total`, hot: kinds.has("search") || kinds.has("gate") },
      { n: "ledger", note: `${num(c.ledger ?? 0)} entries`, hot: !!a && a.cost > 0 },
      { n: "schema_registry", note: `v${S.schema.version ?? "?"} · ${S.schema.fields.length} fields`, hot: false },
      { n: "events", note: `${num(c.events ?? 0)} events`, hot: kinds.has("gate") },
    ];
    $("colls").innerHTML = colls.map((x) => `<div class="coll${x.hot ? " hot" : ""}"><b>${x.n}</b><span>${x.note}</span></div>`).join("");
    const db = steps.find((s) => s.kind === "db");
    $("atlasNote").textContent = db ? db.detail || "" : "";
    $("atlasNote").title = db ? "aggregate: " + (db.detail || "") : "";
  }

  function renderTrace(a) {
    if (!a) {
      $("traceTitle").textContent = "Trace";
      $("traceTotal").textContent = "";
      $("trace").innerHTML = "";
      return;
    }
    const steps = a.steps || [];
    const total = Math.max(a.ms || 1, ...steps.map((s) => s.startMs + s.ms), 1);
    $("traceTitle").textContent = "Trace · " + (PATH[a.path]?.label || "failed").toLowerCase();
    $("traceTotal").textContent = `${secs(a.ms)} · ${usd(a.cost)}`;
    $("trace").innerHTML = steps.map((s) => {
      const k = KIND[s.kind] || { c: "#8A9099" };
      const c = s.ok ? k.c : "#D94A4A";
      const left = (s.startMs / total) * 100, width = (s.ms / total) * 100;
      return `<div class="trow${s.ok ? "" : " bad"}"><span class="tm">+${(s.startMs / 1000).toFixed(2)}s</span>
        <span class="nm" title="${esc(s.name + (s.detail ? " — " + s.detail : ""))}">${esc(s.name)}</span>
        <span class="bar"><i style="--c:${c};left:${left}%;width:${width}%"></i></span>
        <span class="ms">${s.ms ? secs(s.ms) : "—"}</span><span class="cost${s.cost ? " paid" : ""}">${s.cost ? usd(s.cost) : "—"}</span></div>`;
    }).join("");
  }

  function why(a) {
    const steps = a.steps || [];
    const skill = a.skill ? a.skill.split(" ")[0] : null;
    const failed = steps.find((s) => !s.ok);
    const gate = steps.find((s) => s.kind === "gate");
    const nParams = a.params ? Object.keys(a.params).length : 0;
    if (a.path === "cheap")
      return ["Reused a skill, cheap model only",
        `The question matched <code>${esc(skill)}</code>. The cheap model picked it and filled ${nParams} param${nParams === 1 ? "" : "s"}; Atlas ran the tested template. No new query was written.`];
    if (a.path === "mid")
      return ["Escalated to the mid model",
        `The cheap model's attempt did not check out${failed && failed.detail ? ` (${esc(failed.detail)})` : ""}, so the mid model filled <code>${esc(skill)}</code> instead.`];
    if (a.path === "learn") {
      const promoted = a.skill && a.skill.includes("promoted");
      return ["New kind of question: learned a skill",
        `No live skill fit, so the frontier model wrote the pipeline once, then generalized it into <code>${esc(skill)}</code> with typed params. ` +
        (gate ? `The gate checked the cheap model can use it: ${esc(gate.detail)}. ` : "") +
        (promoted ? "Questions like this now go to the cheap model." : "It was not promoted, so the next one will be learned again.")];
    }
    if (a.path === "frontier")
      return ["Skill under repair: frontier answered",
        "The matching skill is flagged after a schema change, so the frontier model answered directly. Once the repaired skill passes the gate, these go back to the cheap model."];
    return ["No answer", esc((a.trace || []).slice(-1)[0] || "Every path failed for this question.")];
  }

  function renderInspector(a) {
    const el = $("inspector");
    if (!a) {
      el.innerHTML = `<span class="label">Inspector</span><div class="why">Why this path?</div><div class="why-t">Pick a question to see why Downshift answered it the way it did, what it cost, and what a frontier-only system would have paid.</div>`;
      return;
    }
    const p = PATH[a.path] || { c: "#D94A4A", label: "FAILED" };
    const [title, text] = why(a);
    const fpa = S.stats.frontierPerAnswer;
    let vs = "—";
    if (a.cost > 0 && (a.path === "cheap" || a.path === "mid")) vs = `<span class="good">${Math.round(fpa / a.cost)}× cheaper</span>`;
    else if (a.path === "learn") vs = `+${usd(Math.max(0, a.cost - fpa))} one-time`;
    else if (a.path === "frontier") vs = "same";
    const model = (a.steps || []).filter((s) => s.model && s.ok).map((s) => s.model).pop();
    const params = a.params && Object.keys(a.params).length
      ? `<div class="params">${Object.entries(a.params).map(([k, v]) => `<span class="k">${esc(k)}</span> = ${esc(v)}`).join("<br>")}</div>` : "";
    let rows = "";
    if (a.rows && a.rows.length) {
      const cols = Object.keys(a.rows[0]).sort((x, y) => (y === "_id") - (x === "_id"));
      const isNum = (c) => a.rows.every((r) => typeof r[c] === "number");
      rows = `<table class="rows"><thead><tr>${cols.map((c) => `<th class="${isNum(c) ? "n" : ""}">${esc(c === "_id" ? "key" : c)}</th>`).join("")}</tr></thead><tbody>` +
        a.rows.slice(0, 6).map((r) => `<tr>${cols.map((c) => `<td class="${isNum(c) ? "n" : ""}">${esc(typeof r[c] === "object" ? JSON.stringify(r[c]) : num(r[c]))}</td>`).join("")}</tr>`).join("") +
        `</tbody></table>${a.rowCount > 6 ? `<span class="muted" style="font-size:12px">+${a.rowCount - 6} more</span>` : ""}`;
    } else rows = `<span class="muted" style="font-size:13px">${a.rows ? "No rows." : "Loading…"}</span>`;
    el.innerHTML = `<span class="label">Inspector</span>
      <span class="pill" style="--c:${p.c}"><span class="dot"></span>${p.label}</span>
      <div class="why">${title}</div><div class="why-t">${text}</div>${params}
      <div class="facts">
        <div class="fact"><span>Skill</span><span>${esc(a.skill ? a.skill.split(" ")[0] : "—")}</span></div>
        <div class="fact"><span>Model</span><span>${esc(model || "—")}</span></div>
        <div class="fact"><span>Cost</span><span>${usd(a.cost)}</span></div>
        <div class="fact"><span>Frontier-only would pay</span><span>${usd(fpa)}</span></div>
        <div class="fact"><span>vs frontier only</span><span>${vs}</span></div>
        <div class="fact"><span>Latency</span><span>${secs(a.ms)}</span></div>
      </div>
      <div class="grow"></div>
      <div class="result"><span class="label">Result</span>${rows}</div>`;
  }

  async function renderLiveDetail() {
    const summary = S.answers.find((x) => oid(x._id) === selected);
    const key = pending ? "pending" : selected + ":" + (summary ? summary.ms : "") + ":" + S.stats.skillsLive + ":" + (S.counts || {}).ledger;
    if (key === renderedKey) return;
    const newAnswer = !renderedKey || renderedKey.split(":")[0] !== (selected || "");
    renderedKey = key;
    if (pending) return;
    const a = summary ? { ...summary, ...(full.get(selected) || {}) } : null;
    renderPath(a);
    if (newAnswer) renderFlow(a);
    renderAtlas(a);
    renderTrace(a);
    renderInspector(a);
    if (a && !a.rows) {
      const f = await selectedAnswer();
      if (f && oid(f._id) === selected) renderInspector({ ...a, ...f });
    }
  }

  // ------------------------------------------------------------------ live: cost race + feed
  function renderRace() {
    const svg = $("raceSvg");
    const W = Math.max(200, svg.clientWidth || 640), H = Math.max(80, svg.clientHeight || 110);
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const race = S.race, fpa = S.stats.frontierPerAnswer;
    const cpa = S.stats.costPerAnswer;
    $("cpa").textContent = cpa == null ? "—" : usd(cpa);
    $("cpaDelta").textContent = cpa == null ? "" : cpa < fpa ? `${Math.round((1 - cpa / fpa) * 100)}% below frontier-only` : "learning: at or above frontier-only";
    $("cpaDelta").style.color = cpa != null && cpa < fpa ? "#00684A" : "#8A6200";
    if (!race.length) {
      svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-size="12" fill="#8A9099" font-family="Geist Mono">cumulative cost appears after the first answer</text>`;
      return;
    }
    const N = Math.max(race.length, 10);
    let cum = 0;
    const pts = race.map((r) => ({ n: r.n, v: (cum += r.cost), path: r.path }));
    const maxY = Math.max(N * fpa * (race.length / N), cum, 0.0001) * 1.08;
    const padL = 4, padR = 70, padT = 8, padB = 16;
    const x = (n) => padL + ((n - 0) / N) * (W - padL - padR);
    const y = (v) => padT + (1 - v / maxY) * (H - padT - padB);
    const last = pts[pts.length - 1];
    const fEnd = last.n * fpa;
    const down = `${x(0)},${y(0)} ` + pts.map((p) => `${x(p.n).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
    const dots = pts.map((p) => `<circle cx="${x(p.n).toFixed(1)}" cy="${y(p.v).toFixed(1)}" r="2.6" fill="${(PATH[p.path] || { c: "#D94A4A" }).c}"><title>q${p.n} · ${p.path}</title></circle>`).join("");
    svg.innerHTML = `
      <line x1="${padL}" y1="${y(0)}" x2="${W - padR}" y2="${y(0)}" stroke="#E4E7EB"/>
      <line x1="${x(0)}" y1="${y(0)}" x2="${x(last.n)}" y2="${y(fEnd)}" stroke="#8A9099" stroke-width="1.5" stroke-dasharray="5 5"/>
      <text x="${x(last.n) + 6}" y="${y(fEnd) + 4}" font-size="11" fill="#5F6670" font-family="Geist Mono">${usd(fEnd, 2)}</text>
      <polyline points="${down}" fill="none" stroke="#00A35C" stroke-width="2.5" stroke-linejoin="round"/>
      ${dots}
      <circle cx="${x(last.n)}" cy="${y(last.v)}" r="5" fill="#00ED64" stroke="#fff" stroke-width="2"/>
      <text x="${x(last.n) + 6}" y="${Math.min(H - padB, y(last.v) + 4)}" font-size="11" font-weight="600" fill="#00684A" font-family="Geist Mono">${usd(last.v, 2)}</text>
      <text x="${padL}" y="${H - 2}" font-size="10" fill="#8A9099" font-family="Geist Mono">q1</text>
      <text x="${x(last.n)}" y="${H - 2}" font-size="10" fill="#8A9099" font-family="Geist Mono" text-anchor="middle">q${last.n}</text>`;
  }

  function eventLine(e) {
    const p = e.payload || {};
    const sk = p.skill ? `${p.skill}${p.version ? "@v" + p.version : ""}` : "";
    switch (e.type) {
      case "answered": return ["answers", `${p.path} · ${p.skill ? p.skill.split(" ")[0] : "—"} · ${usd(p.cost)}`, p.path === "mid" ? "warn" : ""];
      case "skill_candidate": return ["skills", `${sk} candidate`, ""];
      case "skill_promoted": return ["skills", `${sk} promoted · gate ${p.passed}/${p.total}`, ""];
      case "skill_rejected": return ["skills", `${sk} rejected · gate ${p.passed}/${p.total}`, "bad"];
      case "skill_flagged": return ["skills", `${sk} flagged · reads ${(p.fields || []).join(", ")}`, "warn"];
      case "skill_repaired": return ["skills", `${sk} repaired`, ""];
      case "repair_failed": return ["skills", `${sk} repair failed`, "bad"];
      case "schema_changed": return ["schema_registry", `v${p.version} · changed ${(p.fields || []).join(", ")}`, "warn"];
      case "documents_changed": return ["sales", `$rename ${(p.renamed || []).join(" → ")} · ${num(p.count)} docs`, "warn"];
      case "escalated": return ["ledger", `escalated · ${p.reason || ""}`, "warn"];
      default: return ["events", e.type, ""];
    }
  }

  function renderFeed() {
    const evs = S.events.slice(0, 7);
    $("feed").innerHTML = `<span class="label">Atlas activity</span>` + (evs.length ? evs.map((e) => {
      const id = oid(e._id);
      const [c, msg, cls] = eventLine(e);
      const isNew = !firstFeed && !seenEvents.has(id);
      seenEvents.add(id);
      return `<span class="e ${cls}${isNew ? " new" : ""}" title="${esc(msg)}"><span class="t">${hms(e.ts)}</span>  <span class="c">${c}</span>  ${esc(msg)}</span>`;
    }).join("") : `<span class="e"><span class="t">waiting for the first write…</span></span>`);
    firstFeed = false;
  }

  // ------------------------------------------------------------------ repairs
  function skillDoc(id, version) {
    return S.skills.find((s) => s.skillId === id && s.version === version);
  }

  function stagesTemplate(json) {
    try {
      return JSON.parse(json).map((st) => JSON.stringify(st).replace(/,"/g, ', "').replace(/":/g, '": '));
    } catch {
      return [json];
    }
  }

  function diffHTML(before, after) {
    const a = stagesTemplate(before), b = stagesTemplate(after);
    const n = Math.max(a.length, b.length);
    let changed = 0, out = "";
    for (let i = 0; i < n; i++) {
      if (a[i] === b[i]) out += `<div class="ln"><span>${i + 1}</span><span>${esc(a[i])}</span></div>`;
      else {
        changed++;
        if (a[i] != null) out += `<div class="ln del"><span>${i + 1} −</span><span>${esc(a[i])}</span></div>`;
        if (b[i] != null) out += `<div class="ln add"><span>${i + 1} +</span><span>${esc(b[i])}</span></div>`;
      }
    }
    return `<div class="card diff"><div class="h">pipeline template · ${changed} stage${changed === 1 ? "" : "s"} changed</div>${out}</div>`;
  }

  function renderRepairs() {
    const r = S.repair;
    const page = $("repairPage");
    if (!r) {
      page.innerHTML = `<div class="card idle"><h2>No repairs yet</h2>
        <p><b>Simulate schema change</b> renames <span class="mono">storeLocation</span> to <span class="mono">store_location</span> in every sales document. The change stream notices, flags every skill that reads that field, and the frontier model repairs each one. A repair ships only if the new template gives identical answers and passes the gate again.</p>
        <p class="muted" style="font-size:13px">${S.stats.skillsLive ? `${S.stats.skillsLive} skill${S.stats.skillsLive === 1 ? " is" : "s are"} live right now.` : "Tip: replay the 30 questions first so there are skills to repair."}</p></div>`;
      return;
    }
    const flagged = r.flagged || [], results = r.results || [];
    const byKey = (k) => {
      const [id, v] = k.split("@v");
      return results.find((x) => x.skill === id && x.from === Number(v));
    };
    const done = r.stage === "done";
    const allOk = results.length && results.every((x) => x.ok);
    const eqTotal = results.reduce((s, x) => s + (x.equivalence || []).length, 0);
    const eqSame = results.reduce((s, x) => s + (x.equivalence || []).filter((e) => e.same).length, 0);
    const cost = results.reduce((s, x) => s + (x.cost || 0), 0);
    const changed = (r.changed || []).join(" ↔ ");

    // banner
    let cls = "run", c = "#D89B00", title, sub;
    if (!done) {
      title = `Schema v${r.schemaVersion}: ${changed}`;
      sub = r.stage === "repairing" ? `Repairing ${Math.min(results.length + 1, flagged.length)} of ${flagged.length} flagged skills. Flagged skills are off the cheap path; the frontier answers those questions meanwhile.` :
        r.stage === "flagged" ? `${flagged.length} skills read a changed field and were flagged.` : "Change stream noticed the change. Checking which skills read these fields…";
    } else if (!flagged.length) {
      cls = "ok"; c = "#00A35C"; title = `Schema v${r.schemaVersion}: no skills affected`; sub = `No live skill reads ${changed}.`;
    } else if (allOk) {
      cls = "ok"; c = "#00A35C"; title = `${flagged.length} skill${flagged.length === 1 ? "" : "s"} repaired, answers identical`;
      sub = `${eqSame}/${eqTotal} test answers match the old skills exactly · repair cost ${usd(cost)} · back on the cheap path`;
    } else {
      cls = "bad"; c = "#D94A4A"; title = `${results.filter((x) => !x.ok).length} of ${flagged.length} repairs did not ship`;
      sub = "Those skills stay retired from the cheap path; the frontier keeps answering them.";
    }

    // stepper
    const rewrote = results.filter((x) => !(x.error || "").startsWith("llm") && !(x.error || "").startsWith("bad repair")).length;
    const verified = results.filter((x) => (x.equivalence || []).length && x.equivalence.every((e) => e.same)).length;
    const promoted = results.filter((x) => x.ok).length;
    const n = flagged.length;
    const stepState = (doneCond, failCond, active) => (failCond ? "fail" : doneCond ? "done" : active ? "now" : "todo");
    const repairing = r.stage === "repairing";
    const steps = [
      ["Schema change detected", changed || "—", "done"],
      ["Skills flagged", `${n} read ${r.changed ? "a changed field" : "—"}`, stepState(["flagged", "repairing", "done"].includes(r.stage), false, r.stage === "detected")],
      ["Frontier rewrites", `${rewrote}/${n} templates`, stepState(done && rewrote === n, done && rewrote < n, repairing)],
      ["Answers verified", `${verified}/${n} identical`, stepState(done && verified === n, results.some((x) => (x.equivalence || []).some((e) => !e.same)), repairing)],
      ["Gate & promote", `${promoted}/${n} promoted`, stepState(done && promoted === n, done && promoted < n, repairing)],
    ];
    if (!n && done) steps.slice(2).forEach((s) => (s[2] = "done"));

    // cards
    if (!flagged.includes(repairSel)) repairSel = flagged[0] || null;
    let firstWaiting = true, repairingKey = null;
    const cards = flagged.map((k) => {
      const res = byKey(k);
      const [id, v] = k.split("@v");
      const old = skillDoc(id, Number(v)) || {};
      const neu = res && res.to ? skillDoc(id, res.to) || {} : {};
      let status, sc;
      if (res) [status, sc] = res.ok ? [`repaired → v${res.to}`, "promoted"] : ["repair failed", "rejected"];
      else if (repairing && firstWaiting) { [status, sc] = ["repairing…", "flagged"]; firstWaiting = false; repairingKey = k; }
      else [status, sc] = ["waiting", "retired"];
      const oldF = old.fieldsUsed || [], newF = neu.fieldsUsed || [];
      const chips = oldF.map((f) => `<span class="${(r.changed || []).includes(f) && !newF.includes(f) && res ? "gone" : ""}">${esc(f)}</span>`).join("") +
        newF.filter((f) => !oldF.includes(f)).map((f) => `<span class="new">${esc(f)}</span>`).join("");
      return `<button type="button" class="skc${k === repairSel ? " on" : ""}" data-k="${esc(k)}"><span class="top2"><span class="nm">${esc(k)}</span><span class="status ${sc}">${status}</span></span><span class="fchips">${chips}</span></button>`;
    }).join("");

    // detail
    let detail = "";
    const res = repairSel ? byKey(repairSel) : null;
    if (repairSel && !res) {
      detail = `<div class="card idle"><p>${repairSel === repairingKey ? "The frontier model is rewriting this skill's template for the new schema. Verification and the gate run next." : "Waiting for the skills ahead of it."}</p></div>`;
    } else if (res) {
      const eq = res.equivalence || [];
      const same = eq.filter((e) => e.same).length;
      const readOnly = !(res.error || "").startsWith("bad repair");
      const chk = (label, val, ok) => `<div class="chk"><span>${label}</span><span class="${ok == null ? "wait" : ok ? "ok" : "no"}">${val}</span></div>`;
      detail = (res.templateBefore && res.templateAfter ? diffHTML(res.templateBefore, res.templateAfter) : "") +
        `<div class="card equiv"><div style="font-size:13px;font-weight:600">Answers compared: v${res.from} vs repaired</div>
          <div class="eq h"><span>Test question</span><span>before</span><span>after</span><span></span></div>` +
        (eq.length ? eq.map((e) => `<div class="eq"><span title="${esc(e.question)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(e.question)}</span><span class="v" title="${esc(e.before)}">${esc(e.before)}</span><span class="v" title="${esc(e.after)}">${esc(e.after)}</span><span class="${e.same ? "same" : "notsame"}">${e.same ? "SAME" : "DIFF"}</span></div>`).join("") : `<span class="muted" style="font-size:13px">${esc(res.error || "No comparisons ran.")}</span>`) +
        `</div><div class="two"><div class="card checks"><div style="font-size:13px;font-weight:600">Checks</div>
          ${chk("Safety: read-only stages", readOnly ? "✓" : "✗", readOnly)}
          ${chk("Same params as before", eq.length ? "✓" : "—", eq.length ? true : null)}
          ${chk("Answers identical", `${same}/${eq.length}`, eq.length ? same === eq.length : null)}
          ${chk("No output drift", eq.length && same === eq.length ? "✓" : "✗", eq.length ? same === eq.length : null)}
          ${chk("Gate: cheap model", res.gate || "—", res.gate ? res.ok : null)}
          ${chk("Repair cost", usd(res.cost), true)}</div><div style="display:flex;flex-direction:column;gap:14px">` +
        (res.note ? `<div class="note">Frontier note: “${esc(res.note)}”</div>` : "") +
        (res.error ? `<div class="note" style="color:#8A1C12;background:#FCEBEB">${esc(res.error)}</div>` : "") + `</div></div>`;
    }

    // timeline
    const t0 = date(r.ts).getTime() - 3000;
    const types = new Set(["documents_changed", "schema_changed", "skill_flagged", "skill_repaired", "repair_failed", "skill_promoted", "skill_rejected"]);
    const tl = S.events.filter((e) => types.has(e.type) && date(e.ts).getTime() >= t0).reverse()
      .map((e) => `<div><span class="t">${hms(e.ts)}</span>${esc(eventLine(e)[1])}</div>`).join("");

    page.innerHTML = `
      <div class="banner ${cls}" style="--c:${c}"><span class="ic"></span><div><b>${esc(title)}</b><div class="sub">${esc(sub)}</div></div></div>
      <div class="card steps">${steps.map(([b, s, st]) => `<div class="st ${st}"><div class="bar2"></div><b>${b}</b><span>${esc(s)}</span></div>`).join("")}</div>
      ${n ? `<div class="rgrid"><div style="display:flex;flex-direction:column;gap:14px"><div class="skcards">${cards}</div>
        <div class="card"><div class="label" style="padding:14px 16px 0">Timeline</div><div class="tl">${tl || "—"}</div></div></div>
        <div class="rdetail">${detail}</div></div>` : `<div class="card"><div class="label" style="padding:14px 16px 0">Timeline</div><div class="tl">${tl || "—"}</div></div>`}`;
  }
  $("repairPage").addEventListener("click", (e) => {
    const b = e.target.closest(".skc");
    if (!b) return;
    repairSel = b.dataset.k;
    renderRepairs();
  });

  // ------------------------------------------------------------------ skills
  function renderSkills() {
    const rows = [...S.skills].sort((a, b) => a.skillId.localeCompare(b.skillId) || b.version - a.version);
    $("skillsTable").innerHTML = `<thead><tr><th>Skill</th><th>Version</th><th>Status</th><th>Fields read</th><th>Gate</th><th>Answers</th><th>Created by</th></tr></thead><tbody>` +
      (rows.length ? rows.map((s) => `<tr><td class="mono">${esc(s.skillId)}<div class="muted" style="font-family:var(--sans);font-size:12px;margin-top:3px">${esc(s.intent || "")}</div></td>
        <td class="mono">v${s.version}${s.repairedFrom ? ` <span class="muted">(from v${s.repairedFrom})</span>` : ""}</td>
        <td><span class="status ${esc(s.status)}">${esc(s.status)}</span></td>
        <td><span class="fchips">${(s.fieldsUsed || []).map((f) => `<span>${esc(f)}</span>`).join("")}</span></td>
        <td class="mono">${s.gateReport ? `${s.gateReport.passed}/${s.gateReport.total}` : "—"}</td>
        <td class="mono">${s.uses || 0}</td><td class="mono muted">${esc(S.demo ? "demo stand-in" : s.createdBy || "—")}</td></tr>`).join("")
        : `<tr><td colspan="7" class="muted">No skills yet. They appear when the frontier model answers a new kind of question.</td></tr>`) + `</tbody>`;
  }

  // ------------------------------------------------------------------ render + actions
  function render() {
    if (!S) return;
    renderHeader();
    const v = view();
    if (v === "live") {
      renderQuestions();
      renderChips();
      renderLiveDetail();
      renderRace();
      renderFeed();
    } else if (v === "repairs") renderRepairs();
    else renderSkills();
  }

  $("replayBtn").addEventListener("click", async () => {
    try {
      await api("/api/replay", { method: "POST" });
      follow = true;
      location.hash = "#live";
      refreshSoon();
    } catch (e) { toast(e.message); }
  });
  $("schemaBtn").addEventListener("click", async () => {
    try {
      const r = await api("/api/schema-change", { method: "POST", body: "{}" });
      toast(`Renaming ${r.old} → ${r.new} in every sales document`);
      location.hash = "#repairs";
      refreshSoon();
    } catch (e) { toast(e.message); }
  });
  let resetArmed = false;
  $("resetBtn").addEventListener("click", async () => {
    if (!resetArmed) {
      resetArmed = true;
      $("resetBtn").textContent = "Click again to reset";
      setTimeout(() => { resetArmed = false; $("resetBtn").textContent = "Reset"; }, 3000);
      return;
    }
    resetArmed = false;
    $("resetBtn").textContent = "Reset";
    try {
      await api("/api/reset", { method: "POST" });
      full.clear(); selected = null; follow = true; renderedKey = null; seenEvents = new Set(); firstFeed = true;
      $("chips").dataset.key = "";
      toast("Demo reset: fresh data, no skills");
      refresh();
    } catch (e) { toast(e.message); }
  });
  window.addEventListener("resize", () => S && view() === "live" && renderRace());

  showView();
  refresh();
  connect();
  setInterval(refresh, 8000); // safety net if the stream drops
})();
