<script>
  import { INTRO, STEPS, hasSeenTour, markTourSeen, placeTooltip } from "../lib/tour.js";
  import { selection, families, repair } from "../lib/stores.js";

  let { open = $bindable(false) } = $props();
  let phase = $state("intro");   // intro | steps
  let i = $state(0);
  let rect = $state(null);
  let tipEl = $state(null);
  let pos = $state({ top: 0, left: 0, below: true });

  let step = $derived(STEPS[i]);

  function locate() {
    if (phase !== "steps" || !step) return;
    const el = document.querySelector(step.target);
    rect = el ? el.getBoundingClientRect() : null;
    if (rect && tipEl) {
      pos = placeTooltip(rect, { w: tipEl.offsetWidth, h: tipEl.offsetHeight },
                         { w: innerWidth, h: innerHeight });
    }
  }

  // re-measure after the step's view has actually rendered
  $effect(() => {
    if (!open || phase !== "steps") return;
    if (step?.select) {
      const sel = { ...step.select };
      // resolve "some skill" / "the repair" to whatever actually exists right now
      if (sel.kind === "skill" && !sel.id) sel.id = $families[0]?.skillId ?? null;
      if (sel.kind === "repair" && !sel.id) sel.id = $repair ? String($repair.schemaVersion) : null;
      selection.set(sel);
    }
    const t = setTimeout(locate, 60);
    addEventListener("resize", locate);
    addEventListener("scroll", locate, true);
    return () => {
      clearTimeout(t);
      removeEventListener("resize", locate);
      removeEventListener("scroll", locate, true);
    };
  });

  export function start() { phase = "steps"; i = 0; open = true; }
  export function reopen() { phase = "intro"; i = 0; open = true; }

  function finish() {
    open = false;
    markTourSeen();
  }
  const next = () => (i < STEPS.length - 1 ? i++ : finish());
  const back = () => i > 0 && i--;

  if (!hasSeenTour()) open = true;
</script>

<svelte:window onkeydown={(e) => open && e.key === "Escape" && finish()} />

{#if open}
  <div class="scrim" class:spot={phase === "steps" && rect}
       style={rect ? `--x:${rect.left - 6}px;--y:${rect.top - 6}px;--w:${rect.width + 12}px;--h:${rect.height + 12}px` : ""}>
  </div>

  {#if phase === "intro"}
    <div class="card intro" role="dialog" aria-modal="true" aria-labelledby="tourTitle">
      <h2 id="tourTitle">{INTRO.title}</h2>
      <p>{INTRO.body}</p>
      <ol>
        {#each STEPS as s, n}
          <li><b>{n + 1}</b> {s.title}</li>
        {/each}
      </ol>
      <div class="actions">
        <button class="btn ghost" onclick={finish}>Skip</button>
        <button class="btn dark" onclick={start}>Start tour</button>
      </div>
    </div>
  {:else if step}
    <div class="card tip" bind:this={tipEl} role="dialog" aria-modal="true" aria-labelledby="stepTitle"
         style="top:{pos.top}px;left:{pos.left}px">
      <span class="count">{i + 1} of {STEPS.length}</span>
      <h3 id="stepTitle">{step.title}</h3>
      <p>{step.body}</p>
      <div class="actions">
        <button class="btn ghost" onclick={finish}>Skip</button>
        <span class="grow"></span>
        {#if i > 0}<button class="btn" onclick={back}>Back</button>{/if}
        <button class="btn dark" onclick={next}>{i === STEPS.length - 1 ? "Done" : "Next"}</button>
      </div>
    </div>
  {/if}
{/if}

<style>
  .scrim { position: fixed; inset: 0; z-index: 40; background: rgba(21,23,25,.55); }
  /* cut a hole over the target rather than drawing a ring around it */
  .scrim.spot {
    background: transparent;
    box-shadow: 0 0 0 9999px rgba(21,23,25,.55);
    /* `inset` is shorthand for top/right/bottom/left, so it MUST come before them -
       declared after, it reset top/left to auto and the spotlight never moved. */
    inset: auto;
    top: var(--y); left: var(--x); width: var(--w); height: var(--h);
    border-radius: 10px; transition: top .25s ease, left .25s ease, width .25s ease, height .25s ease;
  }
  .card { position: fixed; z-index: 41; background: var(--panel); border: 1px solid var(--line);
          border-radius: var(--r); box-shadow: 0 12px 40px rgba(21,23,25,.22); padding: 20px 22px; }
  .intro { top: 50%; left: 50%; transform: translate(-50%, -50%); width: min(520px, calc(100vw - 32px)); }
  .tip { width: min(360px, calc(100vw - 24px)); }
  h2 { margin: 0 0 8px; font-size: 20px; }
  h3 { margin: 4px 0 6px; font-size: 15px; }
  p { margin: 0; font-size: 13.5px; line-height: 1.6; color: var(--ink-2); }
  ol { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
  li { font-size: 13px; color: var(--ink-2); }
  li b { display: inline-block; width: 20px; font: 600 11px var(--mono); color: var(--muted); }
  .count { font: 11px var(--mono); letter-spacing: .08em; color: var(--muted); text-transform: uppercase; }
  .actions { display: flex; align-items: center; gap: 8px; margin-top: 16px; }
  .grow { flex: 1; }
  .btn { padding: 7px 13px; border: 1px solid var(--faint); border-radius: 6px; background: var(--panel);
         font: inherit; font-size: 13px; color: inherit; cursor: pointer; }
  .btn.dark { background: var(--dark); border-color: var(--dark); color: #fff; }
  .btn.ghost { border-color: transparent; color: var(--muted); }
  @media (prefers-reduced-motion: reduce) { .scrim.spot { transition: none; } }
</style>
