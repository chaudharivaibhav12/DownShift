<script>
  import { onMount } from "svelte";
  import { appState, skills, repair, answers, stats, flowSeenUpTo } from "../../lib/stores.js";
  import { usd, secs } from "../../lib/format.js";

  let host = $state(null);
  let failed = $state(false);
  let orbit = $state(true);
  let ticks = $state([]);
  let hud = $state({ costD: 0, costF: 0, n: 0, paths: { cheap: 0, mid: 0, learn: 0, frontier: 0 } });
  // must be reactive: the seeding effect below has to re-run once the dynamic import resolves
  let scene = $state(null);
  let first = true;

  onMount(() => {
    let live = true;
    import("../../lib/flow/scene.js")
      .then((m) => {
        if (!live) return;
        scene = m;
        m.setHooks({
          land: (a) => {
            hud.n += 1;
            hud.costD += a.cost || 0;
            hud.costF += $stats.frontierPerAnswer || 0;
            if (hud.paths[a.path] != null) hud.paths[a.path] += 1;
            const skill = a.skill ? a.skill.split(" ")[0] : "";
            // lead with the question: a run of same-family answers otherwise reads as one
            // line repeated, which looks stuck rather than like ten questions being answered
            const meta = [skill, usd(a.cost), secs(a.ms)].filter(Boolean).join(" · ");
            const line = { cheap: { tone: "good", head: "Cheap" },
                           mid: { tone: "warn", head: "Escalated" },
                           learn: { tone: "info", head: "Learned" },
                           frontier: { tone: "", head: "Frontier" } }[a.path]
                          || { tone: "bad", head: "No answer" };
            ticks = [{ ...line, question: a.question, meta, id: Math.random() }, ...ticks].slice(0, 4);
          },
          ticker: (e) => (ticks = [{ ...e, id: Math.random() }, ...ticks].slice(0, 4)),
        });
        orbit = m.getOrbit();
        m.attach(host);
      })
      .catch(() => (failed = true));
    return () => {
      live = false;
      flowSeenUpTo.set(scene?.newestTs($answers) ?? $flowSeenUpTo);
      scene?.detach();
    };
  });

  // seed the meter from history on the first sync, then follow live answers
  $effect(() => {
    if (!scene || !$appState) return;
    if (first) {
      hud = { costD: $stats.spent || 0, costF: ($stats.answers || 0) * ($stats.frontierPerAnswer || 0),
              n: $stats.answers || 0, paths: { ...hud.paths, ...($stats.paths || {}) } };
    }
    scene.syncSkills($skills, $repair, first);
    scene.syncRepair($repair, first);
    // on the first sync, replay whatever arrived while the flow was closed
    scene.syncAnswers($answers, first, first ? $flowSeenUpTo : null);
    first = false;
  });

  function toggleOrbit() {
    orbit = !orbit;
    scene?.setOrbit(orbit);
  }
  const toggleFull = () =>
    (document.fullscreenElement ? document.exitFullscreen() : host.requestFullscreen()).catch(() => {});

  let saving = $derived(hud.n && hud.costD < hud.costF
    ? `${Math.round((1 - hud.costD / hud.costF) * 100)}% cheaper over ${hud.n} answers`
    : hud.n ? `learning: ${hud.n} answer${hud.n === 1 ? "" : "s"}, skills pay off from the next one`
    : "ask a question to start");
</script>

<div class="stage" bind:this={host} role="img" aria-label="Live 3D view of questions flowing through Downshift">
  {#if failed}
    <p class="nogl">This view needs WebGL. Every other view shows the same data.</p>
  {/if}

  <section class="meter">
    <div class="k">Spent so far</div>
    <div class="row"><span class="lbl">Frontier only</span>
      <span class="bar"><i style="width:{(hud.costF / Math.max(hud.costF, hud.costD, 1e-9)) * 100}%"></i></span>
      <b>{usd(hud.costF, 2)}</b></div>
    <div class="row"><span class="lbl">Downshift</span>
      <span class="bar"><i class="g" style="width:{(hud.costD / Math.max(hud.costF, hud.costD, 1e-9)) * 100}%"></i></span>
      <b>{usd(hud.costD, 2)}</b></div>
    <div class="save" class:small={!hud.n || hud.costD >= hud.costF}>{saving}</div>
    <div class="paths">
      {#each [["cheap", "#00ED64"], ["mid", "#F2B01E"], ["learn", "#4C6EF5"], ["frontier", "#9AA1AB"]] as [p, c]}
        {#if hud.paths[p] || p !== "frontier"}<span><i style="--c:{c}"></i>{p} {hud.paths[p]}</span>{/if}
      {/each}
    </div>
  </section>

  <div class="tools">
    <button class="btn" aria-pressed={orbit} onclick={toggleOrbit}>Orbit</button>
    <button class="btn" onclick={toggleFull}>Full screen</button>
  </div>

  <section class="ticker" role="status">
    {#each ticks as t (t.id)}
      <div class="tick">
        <b class={t.tone}>{t.head}</b>
        {#if t.question}<span class="q">“{t.question}”</span>{:else}{t.text}{/if}
        {#if t.meta}<span class="m">{t.meta}</span>{/if}
      </div>
    {/each}
  </section>
</div>

<style>
  .stage { position: relative; flex: 1; min-height: 0; border-radius: var(--r); overflow: hidden; background: #07090c; }
  .stage :global(canvas) { display: block; }
  .nogl { position: absolute; inset: 0; display: grid; place-items: center; color: #E8EAED; font-size: 14px; }
  .meter, .ticker, .tools { position: absolute; z-index: 2; color: #E8EAED; }
  .meter { top: 14px; left: 14px; width: 300px; background: rgba(7,9,12,.72); backdrop-filter: blur(6px);
           border: 1px solid #1b2330; border-radius: var(--r); padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
  .k { font: 11px var(--mono); letter-spacing: .08em; color: #8A9099; text-transform: uppercase; }
  .row { display: grid; grid-template-columns: 78px minmax(0, 1fr) 62px; gap: 8px; align-items: center; font: 11.5px var(--mono); }
  .lbl { color: #8A9099; }
  .bar { height: 6px; background: #141b24; border-radius: 3px; overflow: hidden; }
  .bar i { display: block; height: 100%; background: #9AA1AB; transition: width .5s ease; }
  .bar i.g { background: #00ED64; }
  .row b { text-align: right; }
  .save { font: 600 13px var(--sans); color: #7CE0A7; margin-top: 2px; }
  .save.small { font: 11.5px var(--mono); color: #8A9099; font-weight: 400; }
  .paths { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 11px var(--mono); color: #8A9099; }
  .paths i { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--c); margin-right: 5px; }
  .tools { top: 14px; right: 14px; display: flex; gap: 8px; }
  .tools .btn { background: rgba(7,9,12,.72); border: 1px solid #1b2330; color: #E8EAED;
                border-radius: 6px; padding: 6px 12px; font: inherit; font-size: 12.5px; cursor: pointer; }
  .tools .btn[aria-pressed="true"] { border-color: #00ED64; color: #7CE0A7; }
  .ticker { bottom: 14px; left: 14px; right: 14px; display: flex; flex-direction: column-reverse; gap: 5px; }
  .tick { font: 12px var(--mono); background: rgba(7,9,12,.72); border: 1px solid #1b2330;
          border-radius: 6px; padding: 6px 10px; }
  .tick b.good { color: #7CE0A7; } .tick b.warn { color: #F2B01E; }
  .tick b.bad { color: #FF9C9C; } .tick b.info { color: #AFC0FF; }
  .tick { display: flex; align-items: baseline; gap: 8px; }
  .tick .q { flex: 1; min-width: 0; font-family: var(--sans); font-size: 12.5px;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tick .m { color: #8A9099; flex-shrink: 0; }

  /* CSS2D labels are created by the scene at runtime, so Svelte's scoping never reaches them.
     They also must not use --ink / --green-ink: inside the console those are the LIGHT theme
     values, which is why the labels were black on a black scene. */
  .stage :global(.lbl3d) {
    font: 600 11px var(--mono); letter-spacing: .08em; color: #E8EAED;
    text-shadow: 0 0 6px #000, 0 0 2px #000; white-space: nowrap; pointer-events: none; text-align: center;
  }
  .stage :global(.lbl3d small) {
    display: block; font: 10.5px var(--mono); letter-spacing: 0; color: #9AA1AB; margin-top: 2px;
  }
  .stage :global(.lbl3d.skill) {
    font-size: 10.5px; letter-spacing: 0; padding: 3px 7px; border-radius: 5px;
    background: rgba(7,9,12,.7); border: 1px solid rgba(0,237,100,.35); color: #7CE0A7;
  }
  .stage :global(.lbl3d.skill.bad) { border-color: rgba(255,92,92,.5); color: #FF9C9C; }
  .stage :global(.lbl3d.skill.fix) { border-color: rgba(76,110,245,.6); color: #AFC0FF; }
</style>
