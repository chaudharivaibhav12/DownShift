<script>
  import { connection, isDemo, job, stats } from "../lib/stores.js";
  import { replay, schemaChange, toastError } from "../lib/api.js";
  import { usd } from "../lib/format.js";
  import { selection, select, answers, flowSeenUpTo } from "../lib/stores.js";

  let { onHelp } = $props();
  let busy = $derived(!!$job.name);
  let waiting = $derived($selection.kind === "flow" || !$flowSeenUpTo ? 0
    : $answers.filter((a) => new Date(a.ts?.$date || a.ts).getTime() > $flowSeenUpTo).length);

  async function run(fn) {
    try { await fn(); } catch (e) { toastError(e); }
  }
</script>

<header class="top">
  <div class="brand">DOWNSHIFT</div>
  <div class="live" class:off={$connection === "off"}>
    <i></i><span>{$connection === "off" ? "OFFLINE" : "LIVE"}</span>
  </div>
  <span class="grow"></span>
  <span class="stats">
    <span><b>{$stats.answers ?? 0}</b> answers</span>
    <span><b>{$stats.skillsLive ?? 0}</b> skills live</span>
    <span><b>{usd($stats.spent ?? 0, 3)}</b> spent</span>
  </span>
  {#if $isDemo}<span class="demo-tag">offline demo</span>{/if}
  <button class="help" onclick={onHelp} title="How Downshift works" aria-label="How Downshift works">?</button>
  <div class="actions">
    <button class="btn ghost" data-tour="flow" class:on={$selection.kind === "flow"} onclick={() => select("flow", null)}>Flow{#if waiting}<i class="badge">{waiting}</i>{/if}</button>
    <button class="btn" disabled={busy} onclick={() => run(replay)}>
      {$job.name === "replay" ? `Replaying ${$job.done}/${$job.total}…` : "Replay 30 questions"}
    </button>
    <button class="btn dark" data-tour="schema" disabled={busy} onclick={() => run(schemaChange)}>
      {$job.name === "schema-change" ? "Repairing…" : "Simulate schema change"}
    </button>
  </div>
</header>

<style>
  .top { height: 56px; display: flex; align-items: center; gap: 18px; padding: 0 20px;
         background: var(--panel); border-bottom: 1px solid var(--line); flex-shrink: 0; }
  .brand { font-weight: 700; font-size: 15px; letter-spacing: .04em; }
  .live { display: flex; align-items: center; gap: 6px; font: 600 11px var(--mono); color: var(--green-ink); }
  .live i { width: 7px; height: 7px; border-radius: 50%; background: var(--green); }
  .live.off { color: var(--muted); }
  .live.off i { background: var(--faint); }
  .grow { flex: 1; }
  .stats { font: 12px var(--mono); color: var(--muted); display: flex; gap: 16px; white-space: nowrap; }
  .stats b { color: var(--ink); font-weight: 600; }
  .demo-tag { white-space: nowrap; font: 11px var(--mono); color: var(--muted);
              border: 1px dashed var(--faint); border-radius: 999px; padding: 3px 9px; }
  .help { width: 26px; height: 26px; border-radius: 50%; border: 1px solid var(--faint);
          background: var(--panel); color: var(--muted); font: 600 13px var(--sans); cursor: pointer; }
  .help:hover { color: var(--ink); border-color: var(--ink); }
  .actions { display: flex; align-items: center; gap: 8px; padding-left: 16px; border-left: 1px solid var(--line); }
  .btn { padding: 8px 14px; border: 1px solid var(--faint); border-radius: 6px; background: var(--panel);
         font: inherit; font-size: 13px; color: inherit; cursor: pointer; white-space: nowrap; text-decoration: none; }
  .btn.dark { background: var(--dark); border-color: var(--dark); color: #fff; }
  .btn.ghost { border-color: transparent; color: var(--muted); }
  .btn.ghost.on { background: var(--line-2); color: var(--ink); font-weight: 500; }
  .badge { display: inline-grid; place-items: center; min-width: 17px; height: 17px; margin-left: 6px;
           padding: 0 4px; border-radius: 999px; background: var(--cheap); color: #04170d;
           font: 600 10.5px var(--mono); font-style: normal; vertical-align: 1px; }
  .btn:disabled { opacity: .5; cursor: default; }
  @media (max-width: 1180px) { .stats { display: none; } }
</style>
