<script>
  import { kindOf, stepDetail, pathOf } from "../../lib/derive.js";
  import { usd, secs } from "../../lib/format.js";
  import { pending } from "../../lib/stores.js";
  let { answer } = $props();
  let steps = $derived(answer?.steps || []);
  let p = $derived(pathOf(answer));
</script>

<div class="flow" role="region" aria-label="Steps this answer took">
  {#if $pending}
    {#each [0, 1, 2] as i}<div class="skeleton"></div>{/each}
  {:else if !answer}
    <p class="empty">The steps each answer takes appear here: which model, which skill, what ran on Atlas.</p>
  {:else}
    {#each steps as s, i}
      {@const k = kindOf(s)}
      {@const c = s.kind === "frontier" && answer.path === "frontier" ? "#151719" : k.c}
      <div class="wrap" style="animation-delay:{i * 60}ms">
        <div class="node" class:bad={!s.ok} style="--c:{c}">
          <span class="k">{k.k}{s.ok ? "" : " · FAILED"}</span>
          <span class="v">{stepDetail(s)}</span>
          {#if s.ms || s.cost || (s.detail && s.kind !== "db")}
            <span class="s">{[s.ms ? secs(s.ms) : null, s.cost ? usd(s.cost) : null, s.detail && s.kind !== "db" ? s.detail : null].filter(Boolean).join(" · ")}</span>
          {/if}
        </div>
        <span class="arrow" style="--c:{s.ok ? c : 'var(--bad)'}"></span>
      </div>
    {/each}
    <div class="wrap">
      <div class="node" style="--c:{p.c}">
        <span class="k">ANSWER</span>
        <span class="v">{answer.rowCount} row{answer.rowCount === 1 ? "" : "s"}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .flow { width: 250px; flex-shrink: 0; display: flex; flex-direction: column; overflow-y: auto; min-height: 0; }
  .wrap { display: flex; flex-direction: column; align-items: center; opacity: 0; transform: translateY(4px); animation: rise .35s forwards; }
  @keyframes rise { to { opacity: 1; transform: none; } }
  .node { width: 100%; background: #fff; border: 1px solid var(--line); border-left: 3px solid var(--c, var(--faint));
          border-radius: 8px; padding: 6px 10px; text-align: left; }
  .node.bad { border-color: var(--bad); border-left-color: var(--bad); background: var(--bad-bg); }
  .k { display: block; font-size: 10.5px; letter-spacing: .08em; font-weight: 600; color: var(--c, var(--muted)); }
  .node.bad .k { color: var(--bad); }
  .v { display: block; font-size: 12.5px; margin-top: 2px; line-height: 1.35; }
  .s { display: block; font: 11px var(--mono); color: var(--muted); margin-top: 3px; }
  .arrow { width: 2px; height: 8px; background: var(--c, var(--line)); }
  .empty { font-size: 13px; color: var(--muted); line-height: 1.5; margin: 0; }
  .skeleton { height: 46px; border-radius: 8px; margin-bottom: 8px;
              background: linear-gradient(90deg, var(--line-2) 25%, var(--bg) 50%, var(--line-2) 75%);
              background-size: 400% 100%; animation: shimmer 1.4s linear infinite; }
  @keyframes shimmer { to { background-position: -200% 0; } }
  @media (prefers-reduced-motion: reduce) { .wrap, .skeleton { animation: none; opacity: 1; transform: none; } }
</style>
