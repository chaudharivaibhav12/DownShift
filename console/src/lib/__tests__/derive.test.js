import { describe, it, expect } from "vitest";
import { lineage, versionReason, triedTiers, vsFrontier, pathOf, whyAnswer, raceSeries, diffLines, repairSteps, repairBanner, gateOutcomes, previousVersion, eventLine, answersToPlay, newestTs, idOf } from "../derive.js";

describe("lineage", () => {
  const skills = [
    { skillId: "top_stores", version: 1, status: "retired", uses: 2 },
    { skillId: "top_stores", version: 2, status: "promoted", uses: 5, reflectedFrom: 1, reflectionNote: "end dates are exclusive" },
    { skillId: "coupons", version: 1, status: "flagged", uses: 0 },
  ];

  it("groups by family, newest version first", () => {
    const [coupons, top] = lineage(skills);
    expect(coupons.skillId).toBe("coupons");
    expect(top.versions.map((v) => v.version)).toEqual([2, 1]);
  });

  it("reports the live version and summed uses", () => {
    const top = lineage(skills).find((f) => f.skillId === "top_stores");
    expect(top.live.version).toBe(2);
    expect(top.uses).toBe(7);
    expect(top.status).toBe("promoted");
  });

  it("falls back to flagged when no version is promoted", () => {
    expect(lineage(skills).find((f) => f.skillId === "coupons").status).toBe("flagged");
  });

  it("is empty for no skills", () => expect(lineage([])).toEqual([]));
});

describe("versionReason", () => {
  it("prefers a repair over a reflection", () => {
    expect(versionReason({ version: 3, repairedFrom: 2, reflectedFrom: 1 }).kind).toBe("repaired");
  });
  it("quotes the reflection note", () => {
    expect(versionReason({ version: 2, reflectedFrom: 1, reflectionNote: "n" }).text).toContain("“n”");
  });
  it("calls v1 learned", () => expect(versionReason({ version: 1 }).kind).toBe("learned"));
});

describe("triedTiers", () => {
  it("lists tiers attempted but not chosen", () => {
    const a = { path: "mid", steps: [{ kind: "cheap" }, { kind: "mid" }, { kind: "db" }] };
    expect([...triedTiers(a)]).toEqual(["cheap"]);
  });
  it("is empty when the first tier answered", () => {
    expect([...triedTiers({ path: "cheap", steps: [{ kind: "cheap" }] })]).toEqual([]);
  });
});

describe("vsFrontier", () => {
  it("never invents a baseline", () => {
    expect(vsFrontier({ path: "cheap", cost: 0.0001 }, 0).text).toBe("no frontier baseline yet");
    expect(vsFrontier({ path: "cheap", cost: 0.0001 }, null).text).toBe("no frontier baseline yet");
  });
  it("reports a multiple for the cheap path", () => {
    expect(vsFrontier({ path: "cheap", cost: 0.0001 }, 0.0043).text).toBe("43× cheaper than frontier");
  });
  it("reports learning as a one-time premium, never negative", () => {
    expect(vsFrontier({ path: "learn", cost: 0.001 }, 0.0043).text).toContain("$0.0000");
  });
  it("says frontier is the same as frontier-only", () => {
    expect(vsFrontier({ path: "frontier", cost: 0.004 }, 0.0043).text).toBe("same as frontier-only");
  });
});

describe("pathOf", () => {
  it("falls back to FAILED for an unknown path", () => {
    expect(pathOf({ path: "nonsense" }).label).toBe("FAILED");
    expect(pathOf(null).label).toBe("FAILED");
  });
});

describe("whyAnswer", () => {
  it("never returns markup, only text and code segments", () => {
    const a = { path: "cheap", skill: "top_stores@v2 (promoted)", params: { n: 3 } };
    const { parts } = whyAnswer(a);
    expect(parts.every((p) => p.t === "text" || p.t === "code")).toBe(true);
    expect(parts.find((p) => p.t === "code").v).toBe("top_stores@v2");
  });
  it("describes reflection when the gate ran twice", () => {
    const a = { path: "learn", skill: "s@v2 (rejected)", steps: [
      { kind: "gate", detail: "5/8" }, { kind: "gate", detail: "6/8" }, { kind: "check", name: "reflect · tightened dates", detail: "tightened dates" }] };
    expect(whyAnswer(a).title).toContain("then fixed it");
  });
  it("falls back when every path failed", () => {
    expect(whyAnswer({ path: null, trace: ["boom"] }).parts[0].v).toBe("boom");
  });
});

describe("raceSeries", () => {
  it("accumulates cost and projects the frontier-only line", () => {
    const r = raceSeries([{ n: 1, cost: 0.01, path: "learn" }, { n: 2, cost: 0.0001, path: "cheap" }], 0.004);
    expect(r.total).toBeCloseTo(0.0101);
    expect(r.frontierTotal).toBeCloseTo(0.008);
    expect(r.last.n).toBe(2);
  });
  it("is safe with no answers", () => {
    const r = raceSeries([], 0.004);
    expect(r.last).toBe(null);
    expect(r.total).toBe(0);
  });
});

describe("diffLines", () => {
  const A = JSON.stringify([{ $match: { storeLocation: "x" } }, { $group: { _id: 1 } }]);
  const B = JSON.stringify([{ $match: { store_location: "x" } }, { $group: { _id: 1 } }]);
  it("marks only the stage that changed", () => {
    const { lines, changed } = diffLines(A, B);
    expect(changed).toBe(1);
    expect(lines.filter((l) => l.kind === "del")).toHaveLength(1);
    expect(lines.filter((l) => l.kind === "add")).toHaveLength(1);
    expect(lines.filter((l) => l.kind === "same")).toHaveLength(1);
  });
  it("handles a template that gained a stage", () => {
    const { changed, lines } = diffLines(A, JSON.stringify([...JSON.parse(A), { $limit: 3 }]));
    expect(changed).toBe(1);
    expect(lines.at(-1).kind).toBe("add");
  });
  it("degrades to one line when the JSON is unparseable", () => {
    expect(diffLines("not json", "not json").lines).toHaveLength(1);
  });
});

describe("repairSteps", () => {
  it("is empty with no job", () => expect(repairSteps(null)).toEqual([]));
  it("marks later steps todo while detecting", () => {
    const s = repairSteps({ stage: "detected", changed: ["a", "b"], flagged: [], results: [] });
    expect(s[0].state).toBe("done");
    expect(s[4].state).toBe("todo");
  });
  it("fails the verify step when any answer differs", () => {
    const s = repairSteps({ stage: "repairing", flagged: ["x@v1"], results: [{ equivalence: [{ same: false }] }] });
    expect(s[3].state).toBe("fail");
  });
  it("completes every step on a clean run", () => {
    const s = repairSteps({ stage: "done", changed: ["a"], flagged: ["x@v1"],
      results: [{ ok: true, to: 2, equivalence: [{ same: true }] }] });
    expect(s.every((x) => x.state === "done")).toBe(true);
  });
});

describe("repairBanner", () => {
  it("reports a clean repair as ok with the match count", () => {
    const b = repairBanner({ stage: "done", schemaVersion: 3, changed: ["a", "b"], flagged: ["x@v1"],
      results: [{ ok: true, cost: 0.01, equivalence: [{ same: true }, { same: true }] }] });
    expect(b.tone).toBe("ok");
    expect(b.sub).toContain("2/2");
  });
  it("reports partial failure as bad", () => {
    expect(repairBanner({ stage: "done", flagged: ["x@v1", "y@v1"],
      results: [{ ok: true }, { ok: false }] }).tone).toBe("bad");
  });
  it("says so when nothing was affected", () => {
    expect(repairBanner({ stage: "done", schemaVersion: 2, changed: ["z"], flagged: [], results: [] }).tone).toBe("ok");
  });
});

describe("gateOutcomes", () => {
  it("puts failures first so the interesting rows are on top", () => {
    const { outcomes } = gateOutcomes({ gateReport: { passed: 1, total: 2,
      passes: [{ question: "p" }], failures: [{ question: "f", error: "different result" }] } });
    expect(outcomes[0].ok).toBe(false);
    expect(outcomes[1].ok).toBe(true);
  });
  it("flags that the report is only a sample", () => {
    expect(gateOutcomes({ gateReport: { passed: 8, total: 8, passes: new Array(5).fill({ question: "q" }), failures: [] } }).capped).toBe(true);
    expect(gateOutcomes({ gateReport: { passed: 2, total: 2, passes: [{ question: "a" }, { question: "b" }], failures: [] } }).capped).toBe(false);
  });
  it("is safe for a skill that never gated", () => {
    expect(gateOutcomes({}).outcomes).toEqual([]);
    expect(gateOutcomes({}).total).toBe(null);
  });
});

describe("previousVersion", () => {
  const vs = [{ version: 3 }, { version: 1 }, { version: 2 }];
  it("finds the nearest lower version regardless of order", () => {
    expect(previousVersion(vs, 3).version).toBe(2);
  });
  it("returns null for the first version", () => expect(previousVersion(vs, 1)).toBe(null));
});

describe("eventLine", () => {
  it("names the collection each event wrote to", () => {
    expect(eventLine({ type: "skill_promoted", payload: { skill: "s", version: 2, passed: 8, total: 8 } }).coll).toBe("skills");
    expect(eventLine({ type: "schema_changed", payload: { version: 3, fields: ["a"] } }).coll).toBe("schema_registry");
    expect(eventLine({ type: "documents_changed", payload: { renamed: ["a", "b"], count: 5000 } }).coll).toBe("sales");
  });
  it("marks a rejection bad and an escalation warn", () => {
    expect(eventLine({ type: "skill_rejected", payload: { passed: 5, total: 8 } }).tone).toBe("bad");
    expect(eventLine({ type: "escalated", payload: { reason: "x" } }).tone).toBe("warn");
  });
  it("survives an unknown event type", () => {
    expect(eventLine({ type: "something_new" })).toEqual({ coll: "events", text: "something_new", tone: "" });
  });
  it("survives a missing payload", () => {
    expect(() => eventLine({ type: "skill_flagged" })).not.toThrow();
  });
});

describe("date/hms", () => {
  it("unwraps Mongo extended JSON", async () => {
    const { date } = await import("../format.js");
    expect(date({ $date: "2026-09-26T18:54:56.078Z" }).getUTCFullYear()).toBe(2026);
    expect(date("2026-09-26T18:54:56.078Z").getUTCMinutes()).toBe(54);
  });
});

describe("tour", () => {
  it("every step names a target that exists as a data-tour hook", async () => {
    const { STEPS } = await import("../tour.js");
    for (const s of STEPS) expect(s.target).toMatch(/^\[data-tour="[a-z]+"\]$/);
    expect(new Set(STEPS.map((s) => s.id)).size).toBe(STEPS.length);
  });

  it("keeps the tooltip inside the viewport", async () => {
    const { placeTooltip } = await import("../tour.js");
    const vp = { w: 1000, h: 800 };
    const tip = { w: 320, h: 160 };
    // target hard against the left edge
    expect(placeTooltip({ left: 0, right: 40, top: 100, bottom: 140, width: 40 }, tip, vp).left).toBe(12);
    // target hard against the right edge
    expect(placeTooltip({ left: 960, right: 1000, top: 100, bottom: 140, width: 40 }, tip, vp).left).toBe(668);
    // no room below -> flips above
    const p = placeTooltip({ left: 400, right: 600, top: 600, bottom: 700, width: 200 }, tip, vp);
    expect(p.below).toBe(false);
    expect(p.top).toBe(428);
  });

  it("never reports seen when localStorage throws", async () => {
    const { hasSeenTour } = await import("../tour.js");
    const orig = globalThis.localStorage;
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true, get() { throw new Error("blocked"); },
    });
    expect(hasSeenTour()).toBe(false);
    Object.defineProperty(globalThis, "localStorage", { configurable: true, value: orig });
  });
});

describe("answersToPlay", () => {
  const A = (id, t) => ({ _id: { $oid: id }, ts: { $date: new Date(t).toISOString() } });
  const hist = [A("a", 1000), A("b", 2000)];

  it("plays nothing from history on the very first open", () => {
    expect(answersToPlay(hist, new Set(), true, null)).toEqual([]);
  });

  it("plays only what arrived after the watermark", () => {
    const played = answersToPlay([...hist, A("c", 3000)], new Set(), true, 2000);
    expect(played.map(idOf)).toEqual(["c"]);
  });

  it("plays everything unseen once the flow is already open", () => {
    expect(answersToPlay([...hist, A("c", 3000)], new Set(["a"]), false, null).map(idOf)).toEqual(["b", "c"]);
  });

  it("never replays an answer it has already played", () => {
    expect(answersToPlay(hist, new Set(["a", "b"]), false, null)).toEqual([]);
  });

  it("orders playback oldest first regardless of input order", () => {
    expect(answersToPlay([A("c", 3000), A("a", 1000), A("b", 2000)], new Set(), false, null).map(idOf))
      .toEqual(["a", "b", "c"]);
  });

  it("newestTs finds the high-water mark, null when empty", () => {
    expect(newestTs(hist)).toBe(2000);
    expect(newestTs([])).toBe(null);
  });
});
