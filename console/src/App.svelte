<script>
  import { onMount } from "svelte";
  import Header from "./components/Header.svelte";
  import Tour from "./components/Tour.svelte";
  import Rail from "./components/Rail.svelte";
  import Inspector from "./components/Inspector.svelte";
  import AnswerView from "./components/workspace/AnswerView.svelte";
  import AnswerInspector from "./components/parts/AnswerInspector.svelte";
  import EmptyView from "./components/workspace/EmptyView.svelte";
  import RepairView from "./components/workspace/RepairView.svelte";
  import SkillView from "./components/workspace/SkillView.svelte";
  import FlowView from "./components/workspace/FlowView.svelte";
  import { connect, refresh, answerDetail } from "./lib/api.js";
  import { startRouter } from "./lib/router.js";
  import { registerLiveRegion, announce } from "./lib/a11y.js";
  import { selection, answers, pending, flowSeenUpTo } from "./lib/stores.js";
  import { oid } from "./lib/format.js";
  import { pathOf } from "./lib/derive.js";

  let detail = $state(null);
  let tour = $state(null);

  let summary = $derived($selection.kind === "answer"
    ? $answers.find((a) => oid(a._id) === $selection.id) || null : null);
  let answer = $derived(summary ? { ...summary, ...(detail?._id && oid(detail._id) === $selection.id ? detail : {}) } : null);

  // fetch the full answer (rows, steps) once per selection
  $effect(() => {
    const id = $selection.kind === "answer" ? $selection.id : null;
    if (!id) { detail = null; return; }
    let live = true;
    answerDetail(id).then((d) => { if (live) detail = d; }).catch(() => {});
    return () => (live = false);
  });

  // one atomic announcement per completed answer, never a stream of updates
  let lastAnnounced = null;
  $effect(() => {
    if ($pending || !answer?.path || answer._id == null) return;
    const id = oid(answer._id);
    if (id === lastAnnounced) return;
    lastAnnounced = id;
    announce(`Answered by the ${pathOf(answer).name} path, ${answer.rowCount} rows, $${(answer.cost ?? 0).toFixed(4)}.`);
  });

  // history is not something you "missed", so the watermark starts at the newest answer
  let seeded = false;
  $effect(() => {
    if (seeded || !$answers.length) return;
    seeded = true;
    flowSeenUpTo.set($answers.reduce((m, a) => Math.max(m, new Date(a.ts?.$date || a.ts).getTime() || 0), 0));
  });

  onMount(() => {
    const stopRouter = startRouter();
    const stopStream = connect();
    refresh();
    return () => { stopRouter(); stopStream(); };
  });
</script>

<Tour bind:this={tour} />

<div class="shell">
  <Header onHelp={() => tour?.reopen()} />
  <div class="body" class:wide={$selection.kind === "flow"}>
    <Rail />
    <main class="workspace">
      {#if $selection.kind === "flow"}
        <FlowView />
      {:else if $selection.kind === "answer"}
        <AnswerView answer={$pending ? null : answer} />
      {:else if $selection.kind === "skill" && $selection.id}
        <SkillView skillId={$selection.id} />
      {:else if $selection.kind === "repair"}
        <RepairView />
      {:else}
        <EmptyView kind={$selection.kind} />
      {/if}
    </main>
    {#if $selection.kind !== "flow"}
    <Inspector>
      {#if $selection.kind === "answer"}
        <AnswerInspector answer={$pending ? null : answer} />
      {:else}
        <span class="label">Inspector</span>
        <p style="font-size:13px;line-height:1.6;color:var(--muted)">Context for the selected item appears here.</p>
      {/if}
    </Inspector>
    {/if}
  </div>
</div>

<div class="sr" role="status" aria-atomic="true" use:registerLiveRegion></div>

<style>
  .workspace { min-width: 0; min-height: 0; overflow: hidden; padding: 16px 20px; display: flex; flex-direction: column; }
</style>
