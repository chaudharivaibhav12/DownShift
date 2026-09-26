<script>
  import { fetchRun } from "../../lib/api.js";
  import { runs, stats } from "../../lib/stores.js";
  import { runCostPerQuestion, runVsFrontier, pathMix, runAccuracy, PATH } from "../../lib/derive.js";
  import { usd, num, hms } from "../../lib/format.js";

  let { batchId } = $props();
  let run = $state(null);
  let error = $state(null);

  $effect(() => {
    const id = batchId;
    if (!id) { run = null; return; }
    let live = true;
    error = null;
    fetchRun(id).then((r) => live && (run = r)).catch((e) => live && (error = e.message));
    return () => (live = false);
  });

  let cpq = $derived(run ? runCostPerQuestion(run) : null);
  let vs = $derived(run ? runVsFrontier(run, $stats.frontierPerAnswer) : null);
  let mix = $derived(run ? pathMix(run) : []);
  let acc = $derived(run ? runAccuracy(run) : null);

  // every run's cost per question, so this one can be read against the others
  // the server returns newest first; the chart is captioned "oldest on the left", so sort
  let others = $derived([...$runs]
    .sort((a, b) => new Date(a.startedAt?.$date || a.startedAt) - new Date(b.startedAt?.$date || b.startedAt))
    .map((r) => ({ id: r.batchId, v: runCostPerQuestion(r) })).filter((r) => r.v != null));
  let worst = $derived(Math.max(...others.map((o) => o.v), cpq || 0, 1e-9));
</script>

{#if error}
  <div class="idle"><h2>Run not found</h2><p>{error}</p></div>
{:else if !run}
  <div class="idle"><p class="muted">Loading run…</p></div>
{:else}
  <div class="page">
    <header>
      <div>
        <h1>{run.batchId}</h1>
        <p class="sub">{run.kind === "downshift" ? "Downshift run" : "Baseline run"}
          {#if run.modes.length} · {run.modes.join(", ")}{/if}
          {#if run.startedAt} · {hms(run.startedAt)}{/if}</p>
      </div>
      <div class="meta">
        <div><span>Questions</span><b>{run.questions ?? "—"}</b></div>
        <div><span>Model calls</span><b>{num(run.calls)}</b></div>
        <div><span>Total cost</span><b>{usd(run.costUsd, 4)}</b></div>
        <div><span>Per question</span><b>{cpq == null ? "—" : usd(cpq)}</b></div>
      </div>
    </header>

    <div class="card block">
      <span class="label">Which model answered</span>
      <div class="mix">
        {#each mix as m}
          <span class="seg" style="width:{m.pct}%;background:{PATH[m.path]?.c ?? 'var(--faint)'}"
                title="{m.path}: {m.n} calls"></span>
        {/each}
      </div>
      <div class="keys">
        {#each mix as m}
          <span><i style="background:{PATH[m.path]?.c ?? 'var(--faint)'}"></i>{m.path} {m.n} · {Math.round(m.pct)}%</span>
        {/each}
      </div>
    </div>

    <div class="two">
      <div class="card block">
        <span class="label">Versus frontier-only</span>
        {#if vs}
          <div class="big">{vs.percent}%<span>cheaper</span></div>
          <div class="rows">
            <div><span>This run</span><b>{usd(vs.actual, 4)}</b></div>
            <div><span>Frontier-only would pay</span><b>{usd(vs.frontier, 4)}</b></div>
            <div><span>Saved</span><b class="good">{usd(vs.saved, 4)}</b></div>
          </div>
        {:else}
          <p class="note">No frontier baseline recorded yet, so there is nothing to compare against.</p>
        {/if}
      </div>

      <div class="card block">
        <span class="label">Accuracy</span>
        {#if acc.available}
          <div class="big">{acc.passed}<span>of {acc.total} correct</span></div>
        {:else}
          <p class="note">{acc.reason}</p>
        {/if}
      </div>
    </div>

    <div class="card">
      <div class="h"><span class="label">By question family</span></div>
      <table>
        <thead><tr><th>Family</th><th class="n">Calls</th><th class="n">Cost</th><th class="n">Scored</th></tr></thead>
        <tbody>
          {#each run.families as f}
            <tr>
              <td class="mono">{f.family}</td>
              <td class="n">{f.calls}</td>
              <td class="n">{usd(f.costUsd, 4)}</td>
              <td class="n">{f.scored ? `${f.passed}/${f.scored}` : "—"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if others.length > 1}
      <div class="card block">
        <span class="label">Cost per question, across every run</span>
        <div class="bars">
          {#each others as o}
            <div class="bar" class:on={o.id === run.batchId} title="{o.id}: {usd(o.v)}">
              <i style="height:{(o.v / worst) * 100}%"></i>
            </div>
          {/each}
        </div>
        <p class="note">Oldest on the left. This run is highlighted.</p>
      </div>
    {/if}
  </div>
{/if}

<style>
  .page { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; min-height: 0; }
  .idle { padding: 56px 28px; text-align: center; }
  .idle h2 { margin: 0 0 8px; font-size: 20px; }
  .idle p { margin: 0; color: var(--muted); }
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
  h1 { margin: 0; font: 600 18px var(--mono); overflow-wrap: break-word; }
  .sub { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
  .meta { display: flex; gap: 22px; flex-shrink: 0; }
  .meta div { display: flex; flex-direction: column; align-items: flex-end; }
  .meta span { font-size: 11px; letter-spacing: .08em; color: var(--muted); text-transform: uppercase; }
  .meta b { font: 600 17px var(--mono); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); }
  .block { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
  .two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }
  .mix { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--line-2); }
  .seg { display: block; }
  .keys { display: flex; flex-wrap: wrap; gap: 4px 16px; font: 11.5px var(--mono); color: var(--muted); }
  .keys i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .big { font: 600 30px var(--mono); letter-spacing: -.02em; display: flex; align-items: baseline; gap: 8px; }
  .big span { font: 12px var(--mono); color: var(--muted); letter-spacing: 0; }
  .rows { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
  .rows div { display: flex; justify-content: space-between; gap: 12px; }
  .rows span { color: var(--muted); }
  .rows b { font: 12px var(--mono); }
  .rows .good { color: var(--green-ink); }
  .note { margin: 0; font-size: 12.5px; color: var(--muted); line-height: 1.5; }
  .h { padding: 10px 14px; border-bottom: 1px solid var(--line); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; font: 500 10.5px var(--sans); letter-spacing: .06em; color: var(--muted);
       text-transform: uppercase; padding: 8px 14px; border-bottom: 1px solid var(--line); }
  td { padding: 8px 14px; border-bottom: 1px solid var(--line-2); }
  tr:last-child td { border-bottom: 0; }
  .n { text-align: right; }
  td.mono { font: 12px var(--mono); overflow-wrap: anywhere; }
  .bars { display: flex; align-items: flex-end; gap: 4px; height: 70px; }
  .bar { flex: 1; min-width: 3px; height: 100%; display: flex; align-items: flex-end; }
  .bar i { display: block; width: 100%; background: var(--line); border-radius: 2px 2px 0 0; min-height: 2px; }
  .bar.on i { background: var(--cheap); }
  @media (max-width: 1180px) { .two { grid-template-columns: minmax(0, 1fr); } }
</style>
