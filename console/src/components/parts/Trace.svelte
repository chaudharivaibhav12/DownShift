<script>
  import { kindOf } from "../../lib/derive.js";
  import { usd, secs } from "../../lib/format.js";
  import { pending } from "../../lib/stores.js";
  let { answer } = $props();
  let steps = $derived(answer?.steps || []);
  let total = $derived(Math.max(answer?.ms || 1, ...steps.map((s) => s.startMs + s.ms), 1));
</script>

<div class="card trace">
  <div class="head">
    <span class="label">Trace</span>
    <span class="mono muted">{$pending ? "running…" : `${steps.length} step${steps.length === 1 ? "" : "s"}`}</span>
  </div>
  <div class="rows">
    {#if $pending}
      {#each [0, 1, 2, 3] as i}<div class="row skel"><span class="sk" style="width:{[46, 190, 120, 54][i % 4]}px"></span></div>{/each}
    {/if}
    {#each steps as s}
      {@const c = s.ok ? kindOf(s).c : "var(--bad)"}
      <div class="row" class:bad={!s.ok}>
        <span class="tm">+{(s.startMs / 1000).toFixed(2)}s</span>
        <span class="nm" title={s.name + (s.detail ? " — " + s.detail : "")}>{s.name}</span>
        <span class="bar"><i style="--c:{c};left:{(s.startMs / total) * 100}%;width:{(s.ms / total) * 100}%"></i></span>
        <span class="ms">{s.ms ? secs(s.ms) : "—"}</span>
        <span class="cost" class:paid={s.cost}>{s.cost ? usd(s.cost) : "—"}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .trace { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden;
           background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); }
  .head { display: flex; justify-content: space-between; align-items: baseline;
          padding: 10px 14px; border-bottom: 1px solid var(--line); }
  .mono { font: 11px var(--mono); }
  .rows { overflow-y: auto; min-height: 0; scrollbar-gutter: stable; }
  .row { display: grid; grid-template-columns: 58px minmax(150px, 230px) minmax(0, 1fr) 64px 72px;
         align-items: center; gap: 8px; padding: 7px 14px; font-size: 12.5px; border-bottom: 1px solid var(--line-2); }
  .row:last-child { border-bottom: 0; }
  .tm, .ms, .cost { font: 11.5px var(--mono); color: var(--muted); }
  .ms, .cost { text-align: right; white-space: nowrap; }
  .cost.paid { color: var(--ink); }
  .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row.bad .nm { color: var(--bad); }
  .bar { position: relative; height: 8px; background: var(--line-2); border-radius: 2px; }
  .bar i { position: absolute; top: 0; bottom: 0; border-radius: 2px; background: var(--c); min-width: 2px; }
  .row.skel { grid-template-columns: minmax(0, 1fr); }
  .sk { display: block; height: 10px; border-radius: 3px;
        background: linear-gradient(90deg, var(--line-2) 25%, var(--bg) 50%, var(--line-2) 75%);
        background-size: 400% 100%; animation: shimmer 1.4s linear infinite; }
  @keyframes shimmer { to { background-position: -200% 0; } }
  @media (prefers-reduced-motion: reduce) { .sk { animation: none; } }
  @media (max-width: 1400px) { .row { grid-template-columns: 50px minmax(110px, 180px) minmax(0, 1fr) 54px 64px; padding: 7px 10px; gap: 6px; } }
</style>
