<script>
  let { result } = $props();
  let eq = $derived(result?.equivalence || []);
  let same = $derived(eq.filter((e) => e.same).length);
</script>

<div class="card equiv">
  <div class="t">Answers compared: v{result.from} vs repaired · {same}/{eq.length} identical</div>
  <div class="row head"><span>Test question</span><span>before</span><span>after</span><span></span></div>
  {#each eq as e}
    <div class="row">
      <span class="q">{e.question}</span>
      <span class="v">{e.before}</span>
      <span class="v">{e.after}</span>
      <span class={e.same ? "same" : "notsame"}>{e.same ? "SAME" : "DIFF"}</span>
    </div>
  {:else}
    <span class="muted">{result.error || "No comparisons ran."}</span>
  {/each}
</div>

<style>
  .equiv { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
           padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
  .t { font-size: 13px; font-weight: 600; }
  .row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) 56px;
         gap: 10px; font-size: 12.5px; align-items: start; }
  .row.head span { color: var(--muted); font-size: 12px; }
  /* these two values are the proof the repair changed nothing - never truncate them */
  .v { font: 12px var(--mono); white-space: normal; overflow-wrap: break-word; line-height: 1.4; }
  .q { line-height: 1.4; overflow-wrap: break-word; }
  .same { font: 600 11px var(--mono); color: var(--green-ink); }
  .notsame { font: 600 11px var(--mono); color: var(--bad); }
  .muted { color: var(--muted); font-size: 13px; }
  @media (max-width: 1400px) { .row { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) 46px; gap: 8px; } }
</style>
