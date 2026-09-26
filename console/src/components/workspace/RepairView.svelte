<script>
  import TemplateDiff from "../parts/TemplateDiff.svelte";
  import Equivalence from "../parts/Equivalence.svelte";
  import { repair, families, select } from "../../lib/stores.js";
  import { repairSteps, repairBanner } from "../../lib/derive.js";
  import { announce } from "../../lib/a11y.js";

  let r = $derived($repair);
  let banner = $derived(repairBanner(r));
  let steps = $derived(repairSteps(r));
  let flagged = $derived(r?.flagged || []);
  let picked = $state(null);
  let key = $derived(picked && flagged.includes(picked) ? picked : flagged[0] || null);
  let result = $derived.by(() => {
    if (!key || !r) return null;
    const [id, v] = key.split("@v");
    return (r.results || []).find((x) => x.skill === id && x.from === Number(v)) || null;
  });

  // the banner changes stage asynchronously; say it once per transition
  let said = null;
  $effect(() => {
    if (!r) return;
    const sig = `${r.stage}:${(r.results || []).length}`;
    if (sig === said) return;
    said = sig;
    announce(banner ? `${banner.title}. ${banner.sub}` : `Repair stage ${r.stage}.`);
  });
</script>

{#if !r}
  <div class="idle">
    <h2>No repairs yet</h2>
    <p><b>Simulate schema change</b> renames a field in every sales document. The watcher notices, flags every
       skill that reads it, and the frontier model repairs each one. A repair ships only if the new template
       gives identical answers and passes the gate again.</p>
  </div>
{:else}
  <div class="page">
    <div class="banner {banner.tone}">
      <div>
        <b>{banner.title}</b>
        <div class="sub">{banner.sub}</div>
      </div>
    </div>

    <div class="card steps">
      {#each steps as s}
        <div class="st {s.state}">
          <div class="bar"></div>
          <b>{s.title}</b>
          <span>{s.note}</span>
        </div>
      {/each}
    </div>

    <div class="grid">
      <div class="cards">
        {#each flagged as k}
          {@const [id, v] = k.split("@v")}
          {@const res = (r.results || []).find((x) => x.skill === id && x.from === Number(v))}
          <button class="skc" class:on={k === key} onclick={() => (picked = k)}>
            <span class="top">
              <span class="nm">{k}</span>
              <span class="status {res ? (res.ok ? 'promoted' : 'rejected') : 'flagged'}">
                {res ? (res.ok ? `repaired → v${res.to}` : "repair failed") : r.stage === "repairing" ? "repairing…" : "waiting"}
              </span>
            </span>
            <span class="link" role="link" tabindex="0"
                  onclick={(e) => { e.stopPropagation(); select("skill", id); }}
                  onkeydown={(e) => e.key === "Enter" && (e.stopPropagation(), select("skill", id))}>
              see this skill's history →
            </span>
          </button>
        {/each}
      </div>

      <div class="detail">
        {#if result}
          {#if result.templateBefore && result.templateAfter}
            <TemplateDiff before={result.templateBefore} after={result.templateAfter} />
          {/if}
          <Equivalence {result} />
        {:else}
          <div class="idle small"><p>{r.stage === "repairing" ? "The frontier model is rewriting this skill's template for the new schema. Verification and the gate run next." : "Waiting for the skills ahead of it."}</p></div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .page { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; min-height: 0; }
  .idle { padding: 56px 28px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 12px; }
  .idle.small { padding: 28px; }
  .idle h2 { margin: 0; font-size: 20px; font-weight: 600; }
  .idle p { margin: 0; color: var(--muted); max-width: 560px; line-height: 1.6; }
  .banner { border-radius: var(--r); padding: 14px 18px; border: 1px solid var(--line); background: var(--panel); }
  .banner.run { background: var(--mid-bg); border-color: #F0DDA6; }
  .banner.ok { background: var(--cheap-bg); border-color: #BFE6CF; }
  .banner.bad { background: var(--bad-bg); border-color: #F2C4C4; }
  .banner b { font-size: 15px; }
  .sub { font-size: 13px; color: var(--ink-2); margin-top: 2px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); }
  .steps { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); padding: 16px 18px; }
  .st { display: flex; flex-direction: column; gap: 6px; padding-right: 12px; }
  .st .bar { height: 4px; border-radius: 2px; background: var(--line); }
  .st.done .bar { background: var(--cheap); }
  .st.now .bar { background: var(--mid); }
  .st.fail .bar { background: var(--bad); }
  .st b { font-size: 13px; }
  .st.todo b { color: var(--muted); }
  .st span { font: 11.5px var(--mono); color: var(--muted); }
  .grid { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 16px; align-items: start; }
  .cards { display: flex; flex-direction: column; gap: 10px; }
  .skc { text-align: left; background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
         padding: 12px 14px; cursor: pointer; display: flex; flex-direction: column; gap: 8px; font: inherit; }
  .skc.on { border-color: var(--ink); box-shadow: 0 0 0 1px var(--ink); }
  .top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
  .nm { font: 500 13px var(--mono); overflow-wrap: break-word; }
  .status { font: 600 11px var(--mono); padding: 2px 8px; border-radius: 999px; }
  .status.promoted { background: var(--cheap-bg); color: var(--green-ink); }
  .status.flagged { background: var(--mid-bg); color: var(--mid); }
  .status.rejected { background: var(--bad-bg); color: #8A1C12; }
  .link { font-size: 12px; color: var(--learn); cursor: pointer; }
  .link:hover { text-decoration: underline; }
  .detail { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
  @media (max-width: 1180px) { .grid { grid-template-columns: minmax(0, 1fr); } .steps { grid-template-columns: 1fr; gap: 10px; } }
</style>
