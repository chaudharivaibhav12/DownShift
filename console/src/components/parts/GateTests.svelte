<script>
  import { gateOutcomes } from "../../lib/derive.js";
  let { skill } = $props();
  let g = $derived(gateOutcomes(skill));
</script>

<div class="card">
  <div class="h">
    <span class="label">Gate</span>
    <span class="score" class:pass={g.passed === g.total && g.total}>
      {g.total == null ? "never gated" : `${g.passed}/${g.total}`}
      {#if g.model}<span class="model">· {g.model}</span>{/if}
    </span>
  </div>

  {#if g.outcomes.length}
    <ul>
      {#each g.outcomes as o}
        <li class:bad={!o.ok}>
          <span class="mark">{o.ok ? "PASS" : "FAIL"}</span>
          <span class="q">
            {o.question}
            {#if o.params}<span class="p">{Object.entries(o.params).map(([k, v]) => `${k}=${v}`).join(" · ")}</span>{/if}
            {#if o.error}<span class="e">{o.error}</span>{/if}
          </span>
        </li>
      {/each}
    </ul>
    {#if g.capped}
      <p class="note">The gate stores at most five passing and five failing examples, so this is a sample of {g.total} tests, not all of them.</p>
    {/if}
  {:else}
    <p class="note">No gate run recorded for this version.</p>
  {/if}
</div>

<style>
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); }
  .h { display: flex; justify-content: space-between; align-items: baseline; padding: 10px 14px; border-bottom: 1px solid var(--line); }
  .score { font: 600 12px var(--mono); color: var(--mid); }
  .score.pass { color: var(--green-ink); }
  .model { color: var(--muted); font-weight: 400; }
  ul { list-style: none; margin: 0; padding: 0; }
  li { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: 10px; padding: 8px 14px;
       border-bottom: 1px solid var(--line-2); font-size: 12.5px; align-items: start; }
  li:last-child { border-bottom: 0; }
  .mark { font: 600 10.5px var(--mono); color: var(--green-ink); letter-spacing: .06em; }
  li.bad .mark { color: var(--bad); }
  .q { line-height: 1.45; overflow-wrap: break-word; }
  .p, .e { display: block; font: 11.5px var(--mono); margin-top: 3px; }
  .p { color: var(--muted); }
  .e { color: var(--bad); }
  .note { margin: 0; padding: 10px 14px; font-size: 12px; color: var(--muted); line-height: 1.5; }
</style>
