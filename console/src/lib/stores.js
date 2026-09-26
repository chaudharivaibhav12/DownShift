import { writable, derived } from "svelte/store";
import { lineage } from "./derive.js";

/** The /api/state payload, replaced wholesale. The server is the single source of truth. */
export const appState = writable(null);
/** The cursor: one selection for the whole workbench. */
export const selection = writable({ kind: "answer", id: null });
export const connection = writable("off");
/** The in-flight ask. The server does not know about it until the answer lands. */
export const pending = writable(null);
/** Follow the newest answer until the user explicitly picks something. */
export const follow = writable(true);

const from = (fn, fallback) => derived(appState, ($s) => ($s ? fn($s) : fallback));

export const answers = from((s) => s.answers || [], []);
export const skills = from((s) => s.skills || [], []);
export const events = from((s) => s.events || [], []);
export const stats = from((s) => s.stats || {}, {});
export const counts = from((s) => s.counts || {}, {});
export const repair = from((s) => s.repair || null, null);
export const job = from((s) => s.job || { name: null }, { name: null });
export const isDemo = from((s) => !!s.demo, false);

export const families = derived(skills, ($skills) => lineage($skills));

/* Seconds since the in-flight ask started. The interval only exists while something is
   pending, and every view reads the same clock instead of starting its own. */
export const elapsed = derived(pending, ($p, set) => {
  if (!$p) { set(0); return; }
  const t = setInterval(() => set((Date.now() - $p.startedAt) / 1000), 100);
  return () => clearInterval(t);
}, 0);

/* The newest answer that has already been played in the flow. Answers that arrive while the
   flow is closed queue up behind it, so asking from another view still gets its animation. */
export const flowSeenUpTo = writable(null);

/** Run summaries, loaded on demand - they are not part of /api/state. */
export const runs = writable([]);

/** The last failed action, for a visible banner. Screen readers already hear it via announce();
    everyone else saw nothing - the button just re-enabled. */
export const lastError = writable(null);

export function select(kind, id) {
  selection.set({ kind, id });
  follow.set(false);
}
