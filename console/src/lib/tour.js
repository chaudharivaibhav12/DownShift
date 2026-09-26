/* The guided tour. Steps are data so they can be checked without a browser. */

export const INTRO = {
  title: "Welcome to Downshift",
  body: "A frontier model solves a data question once. Downshift turns that answer into a tested skill, so a cheap model can handle every question of that kind from then on — and repairs the skill when the database schema changes.",
};

export const STEPS = [
  {
    id: "ask",
    target: '[data-tour="ask"]',
    title: "Ask a question",
    body: "Anything about the sales data — “Top 3 stores by revenue in March 2016”. The first question of a new kind is the expensive one: the frontier model has to write the query from scratch.",
    select: { kind: "answer", id: null },
  },
  {
    id: "verdict",
    target: '[data-tour="verdict"]',
    title: "Read the verdict",
    body: "Which model answered, what it cost, and how that compares with paying frontier prices every time. The rail underneath shows which tiers were tried before one succeeded.",
    select: { kind: "answer", id: null },
  },
  {
    id: "skills",
    target: '[data-tour="rail"]',
    title: "It becomes a skill",
    body: "A learned query is generalised into a parameterised template, then gated: the cheap model has to use it correctly on generated test questions before it goes live. Open Skills to see each one's full version history.",
    select: { kind: "skill", id: null },
  },
  {
    id: "repair",
    target: '[data-tour="schema"]',
    title: "Break the schema",
    body: "Rename a field across every document and watch the change stream notice, flag every skill that reads it, rewrite each template, and refuse any repair whose answers do not match exactly.",
    select: { kind: "repair", id: null },
  },
  {
    id: "flow",
    target: '[data-tour="flow"]',
    title: "Watch it live",
    body: "The same data as a 3D view: every particle is a real answer taking its real path, every crystal a real skill. It cracks red when a schema change breaks it and turns green when the repair ships.",
    select: { kind: "flow", id: null },
  },
];

const KEY = "downshift.tour.seen";

/* localStorage throws in private mode and in some embedded webviews; the tour is not
   important enough to break the app over. */
export function hasSeenTour() {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}
export function markTourSeen() {
  try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ }
}
export function clearTourSeen() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}

/** Where to put the tooltip so it stays on screen next to its target. */
export function placeTooltip(rect, tip, viewport) {
  const gap = 12;
  const below = rect.bottom + gap + tip.h <= viewport.h;
  const top = below ? rect.bottom + gap : Math.max(gap, rect.top - gap - tip.h);
  let left = rect.left + rect.width / 2 - tip.w / 2;
  left = Math.min(Math.max(gap, left), Math.max(gap, viewport.w - tip.w - gap));
  return { top, left, below };
}
