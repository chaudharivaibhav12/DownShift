export const usd = (n, dp = 4) => (n == null ? "—" : "$" + Number(n).toFixed(dp));
export const secs = (ms) => (ms == null ? "—" : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`);
export const num = (n) => (typeof n === "number" ? n.toLocaleString() : n ?? "—");
/* Mongo extended JSON: dates arrive as {$date: "..."} and ids as {$oid: "..."}. */
export const date = (x) => new Date(x && typeof x === "object" ? x.$date ?? x : x);
export const hms = (ts) => (ts ? date(ts).toLocaleTimeString([], { hour12: false }) : "");
export const oid = (id) => (id && typeof id === "object" ? id.$oid || String(id) : String(id ?? ""));
