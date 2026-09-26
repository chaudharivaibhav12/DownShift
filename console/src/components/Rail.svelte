<script>
  import { answers, families, repair, selection, select, follow, pending, elapsed, runs } from "../lib/stores.js";
  import { fetchRuns } from "../lib/api.js";
  import { pathOf } from "../lib/derive.js";
  import { usd, secs, oid } from "../lib/format.js";
  import AskBox from "./AskBox.svelte";

  const TABS = [
    { key: "answer", label: "Answers" },
    { key: "skill", label: "Skills" },
    { key: "repair", label: "Repairs" },
    { key: "run", label: "Runs" },
  ];

  // The tab IS the selection's kind. Tabs used to be private state, so clicking "Skills"
  // changed the list while the workspace kept showing an answer, and a deep link to a skill
  // left the rail on Answers with nothing highlighted.
  const TAB_KINDS = new Set(TABS.map((t) => t.key));
  let tab = $derived(TAB_KINDS.has($selection.kind) ? $selection.kind : "answer");

  function showTab(kind) {
    if (kind === $selection.kind) return;
    // land on the first row of that kind, or its empty state
    const first = kind === "answer" ? oid($answers[0]?._id)
      : kind === "skill" ? $families[0]?.skillId
      : kind === "run" ? $runs[0]?.batchId
      : $repair ? String($repair.schemaVersion) : null;
    select(kind, first ?? null);
  }

  // run summaries are not part of /api/state, so fetch them the first time the tab is opened
  $effect(() => {
    if (tab !== "run") return;
    fetchRuns().then((r) => {
      runs.set(r);
      // the tab was opened before any run was known, so there was nothing to land on
      if ($selection.kind === "run" && !$selection.id && r[0]) select("run", r[0].batchId);
    }).catch(() => {});
  });
  let q = $state("");

  // follow the newest answer until the user picks something, as the old console did
  $effect(() => {
    // only steal the cursor when it is already on an answer - asking from the flow
    // (or from a skill) should leave you where you are and let that view react
    if ($follow && tab === "answer" && $answers.length && $selection.kind === "answer" && $selection.id !== oid($answers[0]._id)) {
      selection.set({ kind: "answer", id: oid($answers[0]._id) });
    }
  });

  const match = (s) => !q || s.toLowerCase().includes(q.toLowerCase());
  let rows = $derived(
    tab === "answer" ? $answers.filter((a) => match(a.question))
      : tab === "skill" ? $families.filter((f) => match(f.skillId))
      : tab === "run" ? $runs.filter((r) => match(r.batchId))
      : $repair ? [$repair] : []
  );
</script>

<aside class="rail" data-tour="rail">
  <div class="tabs" role="tablist">
    {#each TABS as t}
      <button role="tab" aria-selected={tab === t.key} class:on={tab === t.key}
              onclick={() => showTab(t.key)}>{t.label}</button>
    {/each}
  </div>

  <label class="filter">
    <span class="sr">Filter</span>
    <input placeholder="Filter…" bind:value={q}>
  </label>

  <div class="list">
    {#if $pending && tab === "answer"}
      <div class="item on pending">
        <span class="t">{$pending.question}</span>
        <span class="m"><i class="dot"></i>running… {$elapsed.toFixed(1)}s</span>
      </div>
    {/if}

    {#each rows as r (tab === "answer" ? oid(r._id) : tab === "skill" ? r.skillId : tab === "run" ? r.batchId : "repair")}
      {#if tab === "answer"}
        {@const p = pathOf(r)}
        <button class="item" class:on={$selection.id === oid(r._id)} style="--c:{p.c}"
                onclick={() => select("answer", oid(r._id))}>
          <span class="t">{r.question}</span>
          <span class="m"><i class="dot"></i>{p.label} · {usd(r.cost)} · {secs(r.ms)}</span>
        </button>
      {:else if tab === "skill"}
        <button class="item" class:on={$selection.id === r.skillId}
                style="--c:{r.status === 'promoted' ? 'var(--cheap)' : r.status === 'flagged' ? 'var(--mid)' : 'var(--faint)'}"
                onclick={() => select("skill", r.skillId)}>
          <span class="t mono">{r.skillId}</span>
          <span class="m"><i class="dot"></i>{r.versions.length} version{r.versions.length === 1 ? "" : "s"} · {r.status}</span>
        </button>
      {:else if tab === "run"}
        <button class="item" class:on={$selection.id === r.batchId} style="--c:var(--learn)"
                onclick={() => select("run", r.batchId)}>
          <span class="t mono">{r.batchId}</span>
          <span class="m"><i class="dot"></i>{r.questions ?? r.calls} q · ${r.costUsd.toFixed(4)}</span>
        </button>
      {:else}
        <button class="item" class:on={$selection.kind === "repair"} style="--c:var(--mid)"
                onclick={() => select("repair", String(r.schemaVersion))}>
          <span class="t">Schema v{r.schemaVersion}</span>
          <span class="m"><i class="dot"></i>{r.stage} · {(r.flagged || []).length} flagged</span>
        </button>
      {/if}
    {:else}
      <p class="empty">
        {tab === "answer" ? "No answers yet. Ask a question to start."
          : tab === "skill" ? "No skills yet. They appear when the frontier model answers a new kind of question."
          : tab === "run" ? "No runs yet. A run is one batch of questions: a replay, or python -m scripts.run_downshift."
          : "No repairs yet. Simulate a schema change to see one."}
      </p>
    {/each}
  </div>

  {#if tab === "answer"}<AskBox />{/if}
</aside>

<style>
  .rail { background: var(--panel); border-right: 1px solid var(--line);
          display: flex; flex-direction: column; min-height: 0; }
  .tabs { display: flex; gap: 2px; padding: 10px 12px 0; }
  .tabs button { flex: 1; padding: 7px 4px; border: 0; border-radius: 6px; background: none;
                 font: inherit; font-size: 12.5px; color: var(--muted); cursor: pointer; }
  .tabs button.on { background: var(--line-2); color: var(--ink); font-weight: 500; }
  .filter { display: block; padding: 10px 12px; }
  .filter input { width: 100%; padding: 7px 9px; border: 1px solid var(--faint); border-radius: 6px;
                  font: 12.5px var(--sans); background: var(--bg); color: var(--ink); }
  .list { flex: 1; min-height: 0; overflow-y: auto; padding: 0 8px 10px; }
  .item { display: block; width: 100%; text-align: left; border: 0; background: none;
          border-left: 3px solid transparent; border-radius: 0 6px 6px 0; padding: 9px 10px; cursor: pointer; }
  .item:hover { background: var(--bg); }
  .item.on { background: var(--bg); border-left-color: var(--c, var(--ink)); }
  .t { display: block; font-size: 13px; font-weight: 500; line-height: 1.35; }
  .t.mono { font-family: var(--mono); font-size: 12.5px; overflow-wrap: break-word; }
  .m { display: flex; align-items: center; gap: 6px; margin-top: 5px; font: 11px var(--mono); color: var(--muted); }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c, var(--faint)); flex-shrink: 0; }
  .pending .t { color: var(--muted); }
  .empty { padding: 14px 10px; font-size: 13px; color: var(--muted); line-height: 1.5; }
</style>
