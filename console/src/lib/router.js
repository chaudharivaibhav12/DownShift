/* URL <-> selection, so a skill or an answer can be linked to. Thirty lines beats a dependency. */
import { selection, follow } from "./stores.js";

const KINDS = ["answer", "skill", "repair", "run", "flow"];

function parse(hash) {
  const [kind, ...rest] = (hash || "").replace(/^#\/?/, "").split("/");
  if (!KINDS.includes(kind)) return null;
  const id = decodeURIComponent(rest.join("/") || "");
  return { kind, id: id || null };
}

export function startRouter() {
  const apply = () => {
    if (location.pathname === "/flow" && !location.hash) {
      selection.set({ kind: "flow", id: null });
      follow.set(false);
      return;
    }
    const sel = parse(location.hash);
    if (sel) {
      selection.set(sel);
      follow.set(false);
    }
  };
  apply();
  addEventListener("hashchange", apply);

  const stop = selection.subscribe((sel) => {
    if (!sel || (!sel.id && sel.kind !== "flow")) return;
    const want = sel.kind === "flow" ? "#/flow" : `#/${sel.kind}/${encodeURIComponent(sel.id)}`;
    if (location.hash !== want) history.replaceState(null, "", want);
  });

  return () => {
    removeEventListener("hashchange", apply);
    stop();
  };
}
