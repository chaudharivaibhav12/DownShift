<script>
  import { pathOf, triedTiers } from "../../lib/derive.js";
  let { answer } = $props();
  const POS = { frontier: 0, mid: 1, cheap: 2 };
  let p = $derived(pathOf(answer));
  let tried = $derived(answer ? triedTiers(answer) : new Set());
  let track = $derived.by(() => {
    if (!answer || !p.tier) return null;
    let right = POS[p.tier];
    for (const t of tried) right = Math.max(right, POS[t]);
    if (right <= POS[p.tier]) return null;
    return { left: ["60px", "50%", "calc(100% - 60px)"][POS[p.tier]],
             right: ["calc(100% - 60px)", "50%", "60px"][right] };
  });
</script>

<div class="rail">
  <div class="base"></div>
  {#if track}<div class="track" style="--c:{p.c};left:{track.left};right:{track.right}"></div>{/if}
  {#each [["frontier", "FRONTIER"], ["mid", "MID"], ["cheap", "CHEAP"]] as [tier, label]}
    <div class="stop" class:hit={p.tier === tier} data-tier={tier} style="--c:{p.c}">
      <div class="d" class:hit={p.tier === tier} class:tried={tried.has(tier)}></div>
      <span>{label}</span>
    </div>
  {/each}
</div>

<style>
  .rail { position: relative; height: 38px; }
  .base { position: absolute; left: 60px; right: 60px; top: 10px; height: 2px; background: var(--line); }
  .track { position: absolute; top: 9px; height: 4px; border-radius: 2px; background: var(--c); transition: left .45s ease, right .45s ease; }
  .stop { position: absolute; top: 0; width: 120px; display: flex; flex-direction: column; align-items: center; gap: 6px; }
  .stop[data-tier="frontier"] { left: 0; }
  .stop[data-tier="mid"] { left: calc(50% - 60px); }
  .stop[data-tier="cheap"] { right: 0; }
  .d { width: 22px; height: 22px; border-radius: 50%; background: #fff; border: 2px solid var(--line);
       display: grid; place-items: center; transition: all .3s; }
  .d.hit { background: var(--c); border-color: var(--c); box-shadow: 0 0 0 5px color-mix(in srgb, var(--c) 18%, transparent); }
  .d.tried { border-color: var(--mid); border-style: dashed; }
  .d.tried::after { content: ""; width: 8px; height: 2px; background: var(--mid); }
  span { font: 600 10px var(--mono); color: var(--muted); letter-spacing: .06em; }
  .stop.hit span { color: var(--ink); }
</style>
