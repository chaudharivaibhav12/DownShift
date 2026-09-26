<script>
  import { whyAnswer, vsFrontier } from "../../lib/derive.js";
  import { usd, secs, num } from "../../lib/format.js";
  import { stats, pending } from "../../lib/stores.js";
  let { answer } = $props();

  let why = $derived(answer ? whyAnswer(answer) : null);
  let vs = $derived(answer ? vsFrontier(answer, $stats.frontierPerAnswer) : null);
  let model = $derived((answer?.steps || []).filter((s) => s.model && s.ok).map((s) => s.model).pop());
  let cols = $derived(answer?.rows?.length ? Object.keys(answer.rows[0]).sort((a, b) => (b === "_id") - (a === "_id")) : []);
  const isNum = (rows, c) => rows.every((r) => typeof r[c] === "number");
</script>

<span class="label">Why this path</span>
{#if $pending}
  <p class="t">Working on it. The path, the cost and the reasoning appear here as soon as the answer lands.</p>
{:else if !answer}
  <p class="t">Pick a question to see why Downshift answered it the way it did, what it cost, and what a frontier-only system would have paid.</p>
{:else}
  <p class="t">{#each why.parts as p}{#if p.t === "code"}<code>{p.v}</code>{:else}{p.v}{/if}{/each}</p>

  {#if answer.params && Object.keys(answer.params).length}
    <div class="params">
      {#each Object.entries(answer.params) as [k, v]}<div><span class="k">{k}</span> = {v}</div>{/each}
    </div>
  {/if}

  <div class="facts">
    <div class="fact"><span>Skill</span><span>{answer.skill ? answer.skill.split(" ")[0] : "—"}</span></div>
    <div class="fact"><span>Model</span><span>{model || "—"}</span></div>
    <div class="fact"><span>Cost</span><span>{usd(answer.cost)}</span></div>
    <div class="fact"><span>Frontier-only would pay</span><span>{usd($stats.frontierPerAnswer)}</span></div>
    <div class="fact"><span>vs frontier only</span><span class:good={vs.good}>{vs.text}</span></div>
    <div class="fact"><span>Latency</span><span>{secs(answer.ms)}</span></div>
  </div>

  <div class="result">
    <span class="label">Result</span>
    {#if answer.rows?.length}
      <table>
        <thead><tr>{#each cols as c}<th class:n={isNum(answer.rows, c)}>{c === "_id" ? "key" : c}</th>{/each}</tr></thead>
        <tbody>
          {#each answer.rows.slice(0, 6) as r}
            <tr>{#each cols as c}<td class:n={isNum(answer.rows, c)}>{typeof r[c] === "object" ? JSON.stringify(r[c]) : num(r[c])}</td>{/each}</tr>
          {/each}
        </tbody>
      </table>
      {#if answer.rowCount > 6}<span class="more">+{answer.rowCount - 6} more</span>{/if}
    {:else}
      <span class="more">{answer.rows ? "No rows." : "Loading…"}</span>
    {/if}
  </div>
{/if}

<style>
  .t { font-size: 13px; line-height: 1.55; color: var(--ink-2); margin: 0; }
  code { font: 12px var(--mono); background: var(--line-2); padding: 1px 4px; border-radius: 3px; }
  .params { font: 12px var(--mono); background: var(--bg); border: 1px solid var(--line);
            border-radius: 6px; padding: 10px 12px; line-height: 1.8; }
  .params .k { color: var(--muted); }
  .facts { display: flex; flex-direction: column; gap: 7px; }
  .fact { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
  .fact span:first-child { color: var(--muted); }
  .fact span:last-child { font: 12px var(--mono); text-align: right; overflow-wrap: anywhere; }
  .fact .good { color: var(--green-ink); font-weight: 600; }
  .result { border-top: 1px solid var(--line); padding-top: 12px; display: flex; flex-direction: column; gap: 8px; margin-top: auto; }
  table { width: 100%; border-collapse: collapse; font: 12px var(--mono); }
  th { text-align: left; font: 500 10.5px var(--sans); letter-spacing: .06em; color: var(--muted);
       text-transform: uppercase; padding: 4px 6px 4px 0; border-bottom: 1px solid var(--line); }
  td { padding: 5px 6px 5px 0; border-bottom: 1px solid var(--line-2); overflow-wrap: anywhere; }
  .n { text-align: right; }
  .more { font-size: 12px; color: var(--muted); }
</style>
