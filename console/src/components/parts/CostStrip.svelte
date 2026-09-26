<script>
  import { raceSeries, pathOf, eventLine } from "../../lib/derive.js";
  import { usd, num, hms } from "../../lib/format.js";
  import { appState, stats, counts, events } from "../../lib/stores.js";

  let W = $state(640), H = $state(110);
  let race = $derived($appState?.race || []);
  let fpa = $derived($stats.frontierPerAnswer || 0);
  let cpa = $derived($stats.costPerAnswer);
  let s = $derived(raceSeries(race, fpa));

  const padL = 4, padR = 70, padT = 8, padB = 16;
  let N = $derived(Math.max(race.length, 10));
  let maxY = $derived(Math.max(N * fpa * (race.length / N), s.total, 0.0001) * 1.08);
  const x = (n) => padL + (n / N) * (W - padL - padR);
  const y = (v) => padT + (1 - v / maxY) * (H - padT - padB);

  let colls = $derived([
    { n: "sales", note: `${num($counts.sales ?? 0)} docs` },
    { n: "skills", note: `${$stats.skillsLive ?? 0} live · ${$counts.skills ?? 0} total` },
    { n: "ledger", note: `${num($counts.ledger ?? 0)} entries` },
    { n: "events", note: `${num($counts.events ?? 0)} events` },
  ]);
</script>

<div class="strip">
  <div class="card race">
    <div class="big">
      <span class="label">Cost per answer</span>
      <span class="n">{cpa == null ? "—" : usd(cpa)}</span>
      <span class="d" style="color:{cpa != null && cpa < fpa ? 'var(--green-ink)' : 'var(--mid)'}">
        {cpa == null ? "" : cpa < fpa ? `${Math.round((1 - cpa / fpa) * 100)}% below frontier-only` : "learning: at or above frontier-only"}
      </span>
      <span class="mono muted">last 10 answers</span>
    </div>
    <div class="chart" bind:clientWidth={W} bind:clientHeight={H}>
      <div class="legend">
        <span><i class="dash"></i>frontier only (cumulative)</span>
        <span><i style="background:var(--cheap)"></i>downshift (cumulative)</span>
      </div>
      <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet"
           role="img" aria-label="Cumulative cost, Downshift versus frontier only">
        {#if s.last}
          <line x1={padL} y1={y(0)} x2={W - padR} y2={y(0)} stroke="var(--line)" />
          <line x1={x(0)} y1={y(0)} x2={x(s.last.n)} y2={y(s.frontierTotal)} stroke="var(--faint)" stroke-width="1.5" stroke-dasharray="5 5" />
          <text x={x(s.last.n) + 6} y={y(s.frontierTotal) + 4} font-size="11" fill="var(--muted)" font-family="Geist Mono">{usd(s.frontierTotal, 2)}</text>
          <polyline points={`${x(0)},${y(0)} ` + s.pts.map((p) => `${x(p.n).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ")}
                    fill="none" stroke="var(--cheap)" stroke-width="2.5" stroke-linejoin="round" />
          {#each s.pts as p}
            <circle cx={x(p.n).toFixed(1)} cy={y(p.v).toFixed(1)} r="2.6" fill={pathOf(p).c}><title>q{p.n} · {p.path}</title></circle>
          {/each}
          <circle cx={x(s.last.n)} cy={y(s.last.v)} r="5" fill="var(--green)" stroke="#fff" stroke-width="2" />
          <text x={x(s.last.n) + 6} y={Math.min(H - padB, y(s.last.v) + 4)} font-size="11" font-weight="600" fill="var(--green-ink)" font-family="Geist Mono">{usd(s.last.v, 2)}</text>
          <text x={padL} y={H - 2} font-size="10" fill="var(--muted)" font-family="Geist Mono">q1</text>
          {#if s.last.n > 1}
            <text x={x(s.last.n)} y={H - 2} font-size="10" fill="var(--muted)" font-family="Geist Mono" text-anchor="middle">q{s.last.n}</text>
          {/if}
        {:else}
          <text x={W / 2} y={H / 2} text-anchor="middle" font-size="12" fill="var(--muted)" font-family="Geist Mono">cumulative cost appears after the first answer</text>
        {/if}
      </svg>
    </div>
  </div>

  <div class="card atlas">
    <b>MONGODB ATLAS</b>
    <div class="colls">
      {#each colls as c}<div class="coll"><b>{c.n}</b><span>{c.note}</span></div>{/each}
    </div>
  </div>

  <div class="feed">
    <span class="label">Atlas activity</span>
    {#each $events.slice(0, 6) as e}
      {@const l = eventLine(e)}
      <span class="e {l.tone}"><span class="t">{hms(e.ts)}</span> <span class="c">{l.coll}</span> {l.text}</span>
    {:else}
      <span class="e"><span class="t">waiting for the first write…</span></span>
    {/each}
  </div>
</div>

<style>
  .strip { flex-shrink: 0; display: grid; grid-template-columns: minmax(0, 1fr) 240px 300px; gap: 12px; height: 166px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); min-height: 0; overflow: hidden; }
  .race { display: flex; gap: 22px; padding: 12px 18px; }
  .big { width: 175px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center; gap: 2px; }
  .big .n { font: 600 30px var(--mono); letter-spacing: -.02em; }
  .big .d { font-size: 12px; font-weight: 600; }
  .mono { font: 11px var(--mono); }
  .chart { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .chart svg { flex: 1; min-height: 0; display: block; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font: 11px var(--mono); color: var(--muted); }
  .legend i { display: inline-block; width: 14px; height: 3px; vertical-align: middle; margin-right: 5px; border-radius: 2px; }
  .legend i.dash { background: repeating-linear-gradient(90deg, var(--muted) 0 5px, transparent 5px 10px); }
  .atlas { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
  .atlas > b { font-size: 11px; letter-spacing: .08em; color: var(--green-ink); }
  .colls { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 6px; overflow-y: auto; min-height: 0; }
  .coll { background: var(--bg); border: 1px solid var(--line-2); border-radius: 6px; padding: 6px 8px; }
  .coll b { display: block; font: 500 11px var(--mono); }
  .coll span { display: block; font-size: 10.5px; color: var(--muted); margin-top: 2px; }
  .feed { background: var(--dark); color: #E8EAED; border-radius: var(--r); padding: 12px 14px;
          display: flex; flex-direction: column; gap: 5px; font: 11.5px var(--mono); overflow: hidden; }
  .feed .label { color: var(--faint); }
  .e { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .e .t { color: var(--faint); }
  .e .c { color: #7CE0A7; }
  .e.warn .c { color: #F2C14E; }
  .e.bad .c { color: #F08A8A; }
  @media (max-width: 1180px) { .strip { grid-template-columns: minmax(0, 1fr) 220px; } .feed { display: none; } }
  @media (max-width: 860px) { .strip { grid-template-columns: minmax(0, 1fr); height: auto; } .atlas { display: none; } }
</style>
