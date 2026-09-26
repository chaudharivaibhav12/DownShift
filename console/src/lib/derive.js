/* Pure derivations. Everything here is unit-tested; the components are not. */

export const PATH = {
  cheap: { c: "#00A35C", label: "CHEAP", tier: "cheap", name: "cheap model" },
  mid: { c: "#8A6200", label: "MID", tier: "mid", name: "mid model" },
  learn: { c: "#3B5BDB", label: "LEARN", tier: "frontier", name: "frontier model, learned" },
  frontier: { c: "#151719", label: "FRONTIER", tier: "frontier", name: "frontier model" },
};
export const FAILED = { c: "#C0392B", label: "FAILED", tier: null, name: "no path" };

export const pathOf = (a) => (a && PATH[a.path]) || FAILED;

/** Tiers that were attempted but did not produce the answer. */
export function triedTiers(a) {
  const hit = pathOf(a).tier;
  const t = new Set();
  for (const s of a?.steps || []) {
    if ((s.kind === "cheap" || s.kind === "mid") && s.kind !== hit) t.add(s.kind);
  }
  return t;
}

/** The one comparison the project exists to make. Never invents a baseline. */
export function vsFrontier(a, frontierPerAnswer) {
  if (!frontierPerAnswer) return { text: "no frontier baseline yet", good: false };
  if (a.cost > 0 && (a.path === "cheap" || a.path === "mid")) {
    return { text: `${Math.round(frontierPerAnswer / a.cost)}× cheaper than frontier`, good: true };
  }
  if (a.path === "learn") {
    return { text: `+${usdish(Math.max(0, a.cost - frontierPerAnswer))} one-time, reused from here`, good: false };
  }
  if (a.path === "frontier") return { text: "same as frontier-only", good: false };
  return { text: "—", good: false };
}
const usdish = (n) => "$" + n.toFixed(4);

/** Why a given version of a skill exists. Derived only from fields already on the document. */
export function versionReason(s) {
  if (s.repairedFrom) return { kind: "repaired", text: `repaired from v${s.repairedFrom} after a schema change` };
  if (s.reflectedFrom) return { kind: "reflected", text: s.reflectionNote ? `reflected from v${s.reflectedFrom}: “${s.reflectionNote}”` : `reflected from v${s.reflectedFrom}` };
  if (s.version === 1) return { kind: "learned", text: "learned from the first question of this kind" };
  return { kind: "new", text: "new version" };
}

/** Skills grouped into families, newest version first, with the reason each version exists. */
export function lineage(skills = []) {
  const byId = new Map();
  for (const s of skills) {
    if (!byId.has(s.skillId)) byId.set(s.skillId, []);
    byId.get(s.skillId).push(s);
  }
  return [...byId.entries()]
    .map(([skillId, versions]) => {
      const sorted = [...versions].sort((a, b) => b.version - a.version);
      const live = sorted.find((v) => v.status === "promoted") || null;
      return {
        skillId,
        live,
        status: live ? "promoted" : sorted.some((v) => v.status === "flagged") ? "flagged" : sorted[0]?.status || "unknown",
        uses: sorted.reduce((n, v) => n + (v.uses || 0), 0),
        versions: sorted.map((v) => ({ ...v, reason: versionReason(v) })),
      };
    })
    .sort((a, b) => a.skillId.localeCompare(b.skillId));
}

export const KIND = {
  search: { k: "SKILL SEARCH", c: "#5F6670" },
  cheap: { k: "CHEAP MODEL", c: "#00A35C" },
  mid: { k: "MID MODEL", c: "#8A6200" },
  frontier: { k: "FRONTIER MODEL", c: "#3B5BDB" },
  db: { k: "ATLAS", c: "#00684A" },
  check: { k: "CHECK", c: "#5F6670" },
  gate: { k: "PROMOTION GATE", c: "#3B5BDB" },
};
export const kindOf = (s) => KIND[s.kind] || { k: String(s.kind || "").toUpperCase(), c: "#5F6670" };

/** The step label without its "name · detail" prefix. */
export const stepDetail = (s) => {
  const i = (s.name || "").indexOf(" · ");
  return i >= 0 ? s.name.slice(i + 3) : s.name;
};

const txt = (v) => ({ t: "text", v });
const code = (v) => ({ t: "code", v });

/** Plain-language account of why an answer took the path it did.
    Returns segments rather than HTML so the view never interpolates markup. */
export function whyAnswer(a) {
  const steps = a.steps || [];
  const skill = a.skill ? a.skill.split(" ")[0] : "—";
  const failed = steps.find((s) => !s.ok);
  const gate = steps.find((s) => s.kind === "gate");
  const nParams = a.params ? Object.keys(a.params).length : 0;

  if (a.path === "cheap") {
    return { title: "Reused a skill, cheap model only", parts: [
      txt("The question matched "), code(skill),
      txt(`. The cheap model picked it and filled ${nParams} param${nParams === 1 ? "" : "s"}; Atlas ran the tested template. No new query was written.`)] };
  }
  if (a.path === "mid") {
    return { title: "Escalated to the mid model", parts: [
      txt(`The cheap model's attempt did not check out${failed?.detail ? ` (${failed.detail})` : ""}, so the mid model filled `),
      code(skill), txt(" instead.")] };
  }
  if (a.path === "learn") {
    const promoted = a.skill?.includes("promoted");
    const gates = steps.filter((s) => s.kind === "gate");
    const reflect = steps.find((s) => /reflect/.test(s.name || ""));
    if (reflect && gates.length > 1) {
      return { title: "New kind of question: learned a skill, then fixed it", parts: [
        txt(`No live skill fit, so the frontier model wrote the pipeline once and generalized it into a skill. The gate rejected v1 (${gates[0].detail}): the frontier compared the cheap model's passing and failing traces (“${reflect.detail || ""}”), rewrote the descriptions, and v2 re-gated at ${gates[1].detail}. `),
        code(skill), txt(promoted ? " now goes to the cheap model." : " was still not promoted.")] };
    }
    return { title: "New kind of question: learned a skill", parts: [
      txt("No live skill fit, so the frontier model wrote the pipeline once, then generalized it into "),
      code(skill),
      txt(` with typed params. ${gate ? `The gate checked the cheap model can use it: ${gate.detail}. ` : ""}${promoted ? "Questions like this now go to the cheap model." : "It was not promoted, so the next one will be learned again."}`)] };
  }
  if (a.path === "frontier") {
    return { title: "Skill under repair: frontier answered", parts: [
      txt("The matching skill is flagged after a schema change, so the frontier model answered directly. Once the repaired skill passes the gate, these go back to the cheap model.")] };
  }
  return { title: "No answer", parts: [txt((a.trace || []).slice(-1)[0] || "Every path failed for this question.")] };
}

/** Cumulative cost series: downshift actual vs frontier-only, for the race chart. */
export function raceSeries(race = [], frontierPerAnswer = 0) {
  let cum = 0;
  const pts = race.map((r) => ({ n: r.n, v: (cum += r.cost), path: r.path }));
  const last = pts[pts.length - 1] || null;
  return { pts, total: cum, frontierTotal: last ? last.n * frontierPerAnswer : 0, last };
}

/** A pipeline template (stored as a JSON string) split into readable stage lines. */
export function stagesOf(json) {
  try {
    return JSON.parse(json).map((st) => JSON.stringify(st).replace(/,"/g, ', "').replace(/":/g, '": '));
  } catch {
    return [json];
  }
}

/** Line-by-line diff of two templates. Positional, like the original: stages are ordered. */
export function diffLines(before, after) {
  const a = stagesOf(before), b = stagesOf(after);
  const out = [];
  let changed = 0;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (a[i] === b[i]) out.push({ n: i + 1, kind: "same", text: a[i] });
    else {
      changed++;
      if (a[i] != null) out.push({ n: i + 1, kind: "del", text: a[i] });
      if (b[i] != null) out.push({ n: i + 1, kind: "add", text: b[i] });
    }
  }
  return { lines: out, changed };
}

/** The five repair stages, with each one's state derived from the job document. */
export function repairSteps(r) {
  if (!r) return [];
  const flagged = r.flagged || [], results = r.results || [];
  const n = flagged.length;
  const done = r.stage === "done";
  const repairing = r.stage === "repairing";
  const rewrote = results.filter((x) => !(x.error || "").startsWith("llm") && !(x.error || "").startsWith("bad repair")).length;
  const verified = results.filter((x) => (x.equivalence || []).length && x.equivalence.every((e) => e.same)).length;
  const promoted = results.filter((x) => x.ok).length;
  const st = (doneCond, failCond, active) => (failCond ? "fail" : doneCond ? "done" : active ? "now" : "todo");

  return [
    { title: "Schema change detected", note: (r.changed || []).join(" ↔ ") || "—", state: "done" },
    { title: "Skills flagged", note: `${n} read a changed field`,
      state: st(["flagged", "repairing", "done"].includes(r.stage), false, r.stage === "detected") },
    { title: "Frontier rewrites", note: `${rewrote}/${n} templates`, state: st(done && rewrote === n, done && rewrote < n, repairing) },
    { title: "Answers verified", note: `${verified}/${n} identical`,
      state: st(done && verified === n, results.some((x) => (x.equivalence || []).some((e) => !e.same)), repairing) },
    { title: "Gate & promote", note: `${promoted}/${n} promoted`, state: st(done && promoted === n, done && promoted < n, repairing) },
  ];
}

/** Banner copy for a repair job. */
export function repairBanner(r) {
  if (!r) return null;
  const flagged = r.flagged || [], results = r.results || [];
  const changed = (r.changed || []).join(" ↔ ");
  if (r.stage !== "done") {
    return { tone: "run", title: `Schema v${r.schemaVersion}: ${changed}`,
      sub: r.stage === "repairing"
        ? `Repairing ${Math.min(results.length + 1, flagged.length)} of ${flagged.length} flagged skills. Flagged skills are off the cheap path; the frontier answers those questions meanwhile.`
        : r.stage === "flagged" ? `${flagged.length} skills read a changed field and were flagged.`
        : "Change stream noticed the change. Checking which skills read these fields…" };
  }
  if (!flagged.length) return { tone: "ok", title: `Schema v${r.schemaVersion}: no skills affected`, sub: `No live skill reads ${changed}.` };
  const eqTotal = results.reduce((s, x) => s + (x.equivalence || []).length, 0);
  const eqSame = results.reduce((s, x) => s + (x.equivalence || []).filter((e) => e.same).length, 0);
  const cost = results.reduce((s, x) => s + (x.cost || 0), 0);
  if (results.length && results.every((x) => x.ok)) {
    return { tone: "ok", title: `${flagged.length} skill${flagged.length === 1 ? "" : "s"} repaired, answers identical`,
      sub: `${eqSame}/${eqTotal} test answers match the old skills exactly · repair cost $${cost.toFixed(4)} · back on the cheap path` };
  }
  return { tone: "bad", title: `${results.filter((x) => !x.ok).length} of ${flagged.length} repairs did not ship`,
    sub: "Those skills stay off the cheap path; the frontier keeps answering them." };
}

/** Per-test gate outcomes, from the report the gate stored.
    The report keeps only the first 5 passes and 5 failures, so this is a sample, not the whole run:
    `capped` says so, and the view must not imply otherwise. */
export function gateOutcomes(skill) {
  const r = skill?.gateReport;
  if (!r) return { outcomes: [], passed: null, total: null, capped: false, model: null };
  const outcomes = [
    ...(r.failures || []).map((f) => ({ ok: false, question: f.question, error: f.error, modelOutput: f.modelOutput })),
    ...(r.passes || []).map((p) => ({ ok: true, question: p.question, params: p.params })),
  ];
  return {
    outcomes,
    passed: r.passed, total: r.total, model: r.model,
    capped: outcomes.length < (r.total ?? 0),
  };
}

/** The version immediately before this one, for a template diff. */
export function previousVersion(versions, version) {
  return versions.filter((v) => v.version < version).sort((a, b) => b.version - a.version)[0] || null;
}

/** One activity-feed line per event: which collection was written, and what happened.
    Returns data, never markup. */
export function eventLine(e) {
  const p = e.payload || {};
  const sk = p.skill ? `${p.skill}${p.version ? ` v${p.version}` : ""}` : "";
  const money = (n) => (n == null ? "" : "$" + Number(n).toFixed(4));
  switch (e.type) {
    case "answered": return { coll: "answers", text: `${p.path} · ${p.skill ? p.skill.split(" ")[0] : "—"} · ${money(p.cost)}`, tone: p.path === "mid" ? "warn" : "" };
    case "skill_candidate": return { coll: "skills", text: `${sk} candidate`, tone: "" };
    case "skill_promoted": return { coll: "skills", text: `${sk} promoted · gate ${p.passed}/${p.total}`, tone: "good" };
    case "skill_rejected": return { coll: "skills", text: `${sk} rejected · gate ${p.passed}/${p.total}`, tone: "bad" };
    case "skill_reflected": return { coll: "skills", text: `${sk} reflected from v${p.fromVersion}${p.note ? ` · ${p.note}` : ""}`, tone: "warn" };
    case "skill_flagged": return { coll: "skills", text: `${sk} flagged · reads ${(p.fields || []).join(", ")}`, tone: "warn" };
    case "skill_repaired": return { coll: "skills", text: `${sk} repaired`, tone: "good" };
    case "skill_too_narrow": return { coll: "skills", text: `${sk} could not express the question`, tone: "warn" };
    case "repair_failed": return { coll: "skills", text: `${sk} repair failed`, tone: "bad" };
    case "schema_changed": return { coll: "schema_registry", text: `v${p.version} · changed ${(p.fields || []).join(", ")}`, tone: "warn" };
    case "documents_changed": return { coll: "sales", text: `$rename ${(p.renamed || []).join(" → ")} · ${p.count} docs`, tone: "warn" };
    case "escalated": return { coll: "ledger", text: `escalated · ${p.reason || ""}`, tone: "warn" };
    default: return { coll: "events", text: e.type, tone: "" };
  }
}

export const tsOf = (a) => new Date(a?.ts?.$date || a?.ts).getTime() || 0;
export const idOf = (a) => (a?._id && typeof a._id === "object" ? a._id.$oid : a?._id);

/** Which answers the flow should animate, oldest first.
    - not the first sync: anything not seen yet
    - first sync after opening the flow: only what arrived after the watermark, so history
      sits still but anything asked while the flow was closed still gets played */
export function answersToPlay(answers, seen, first, sinceTs) {
  const fresh = answers.filter((a) => !seen.has(idOf(a))).sort((x, y) => tsOf(x) - tsOf(y));
  if (!first) return fresh;
  return sinceTs ? fresh.filter((a) => tsOf(a) > sinceTs) : [];
}

export const newestTs = (answers = []) => answers.reduce((m, a) => Math.max(m, tsOf(a)), 0) || null;
