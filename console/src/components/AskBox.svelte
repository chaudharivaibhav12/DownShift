<script>
  import { ask } from "../lib/api.js";
  import { pending, appState, follow } from "../lib/stores.js";
  let q = $state("");
  let error = $state(null);
  let suggestions = $derived(($appState?.suggestions || []).slice(0, 4));

  async function submit(e) {
    e?.preventDefault();
    const question = q.trim();
    if (!question || $pending) return;
    error = null;
    follow.set(true);
    try { await ask(question); q = ""; } catch (err) { error = err.message; }
  }
</script>

<form class="askbox" data-tour="ask" onsubmit={submit} autocomplete="off">
  <label class="label" for="askInput">Ask</label>
  <div class="row">
    <input id="askInput" bind:value={q} aria-describedby="askErr" disabled={!!$pending}
           placeholder="Top 3 stores by revenue in 2016">
    <button class="btn dark" disabled={!!$pending}>{$pending ? "Asking…" : "Ask"}</button>
  </div>
  {#if error}<div class="err" id="askErr" role="alert">{error}</div>{/if}
  <div class="chips">
    {#each suggestions as s}
      <button type="button" class="chip" onclick={() => { q = s; submit(); }}>{s}</button>
    {/each}
  </div>
</form>

<style>
  .askbox { border-top: 1px solid var(--line); padding: 14px 14px 16px; display: flex; flex-direction: column; gap: 8px; }
  .row { display: flex; gap: 6px; }
  input { flex: 1; min-width: 0; padding: 10px 11px; border: 1px solid var(--faint); border-radius: 6px;
          font: 13px var(--sans); background: var(--bg); color: var(--ink); }
  input:focus { outline: none; border-color: var(--ink); background: #fff; }
  .btn { padding: 8px 14px; border: 1px solid var(--dark); border-radius: 6px; background: var(--dark);
         color: #fff; font: inherit; font-size: 13px; cursor: pointer; }
  .btn:disabled { opacity: .5; cursor: default; }
  .err { font-size: 12px; color: var(--bad); }
  .chips { display: flex; flex-direction: column; gap: 4px; }
  .chip { text-align: left; border: 1px solid var(--line); background: var(--panel); border-radius: 6px;
          padding: 6px 9px; font: inherit; font-size: 12px; line-height: 1.35; max-height: calc(2.7em + 12px);
          color: var(--ink-2); cursor: pointer; display: -webkit-box; -webkit-line-clamp: 2;
          -webkit-box-orient: vertical; overflow: hidden; }
  .chip:hover { border-color: var(--faint); color: var(--ink); }
</style>
