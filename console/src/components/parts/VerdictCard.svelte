<script>
  import PathRail from "./PathRail.svelte";
  import { pathOf, whyAnswer, vsFrontier } from "../../lib/derive.js";
  import { usd, secs } from "../../lib/format.js";
  import { pending, stats, elapsed } from "../../lib/stores.js";

  let { answer } = $props();

  let p = $derived(pathOf(answer));
  let why = $derived(answer ? whyAnswer(answer) : null);
  let vs = $derived(answer ? vsFrontier(answer, $stats.frontierPerAnswer) : null);
  let model = $derived((answer?.steps || []).filter((s) => s.model && s.ok).map((s) => s.model).pop());
</script>

<div class="card verdict" data-tour="verdict">
  <div class="head">
    <div class="main">
      {#if $pending}
        <div class="line">Working on it…</div>
        <div class="meta">{$pending.question}</div>
      {:else if answer && why}
        <div class="line">{why.title}</div>
        <div class="meta"><span class="tier" style="--c:{p.c}">{p.name}</span>{model ? ` · ${model}` : ""} · {secs(answer.ms)}</div>
      {:else}
        <div class="line">Ask a question to start</div>
        <div class="meta">The first question of a kind is learned by the frontier model; the ones after it go to the cheap model.</div>
      {/if}
    </div>
    <div class="cost">
      <span class="n">{$pending ? $elapsed.toFixed(1) + "s" : answer ? usd(answer.cost) : "—"}</span>
      <span class="sub" class:good={vs?.good}>{$pending ? "elapsed" : (vs?.text ?? "")}</span>
    </div>
  </div>
  <PathRail answer={$pending ? null : answer} />
</div>

<style>
  .verdict { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
             padding: 16px 22px 12px; display: flex; flex-direction: column; gap: 12px; }
  .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
  .main { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .line { font-size: 21px; font-weight: 600; line-height: 1.25; letter-spacing: -.01em; }
  .meta { font: 12.5px var(--mono); color: var(--muted); line-height: 1.45; }
  .tier { color: var(--c); font-weight: 600; }
  .cost { flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
  .n { font: 600 28px var(--mono); letter-spacing: -.02em; line-height: 1; }
  .sub { font: 12px var(--mono); color: var(--muted); }
  .sub.good { color: var(--green-ink); font-weight: 600; }
</style>
