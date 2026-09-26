<script>
  import GateTests from "../parts/GateTests.svelte";
  import TemplateDiff from "../parts/TemplateDiff.svelte";
  import { families } from "../../lib/stores.js";
  import { previousVersion, stagesOf } from "../../lib/derive.js";

  let { skillId } = $props();
  let family = $derived($families.find((f) => f.skillId === skillId) || null);
  let pickedVersion = $state(null);
  let current = $derived.by(() => {
    if (!family) return null;
    return family.versions.find((v) => v.version === pickedVersion) || family.versions[0];
  });
  let prev = $derived(family && current ? previousVersion(family.versions, current.version) : null);
</script>

{#if !family}
  <div class="idle"><h2>Skill not found</h2><p>It may have been reset. Pick another from the rail.</p></div>
{:else}
  <div class="page">
    <header>
      <div>
        <h1>{family.skillId}</h1>
        <p class="intent">{current?.intent || "—"}</p>
      </div>
      <div class="meta">
        <div><span>Live</span><b>{family.live ? `v${family.live.version}` : "none"}</b></div>
        <div><span>Versions</span><b>{family.versions.length}</b></div>
        <div><span>Answers</span><b>{family.uses}</b></div>
      </div>
    </header>

    <div class="grid">
      <ol class="timeline">
        {#each family.versions as v}
          <li>
            <button class="v" class:on={v.version === current.version} onclick={() => (pickedVersion = v.version)}>
              <span class="top">
                <b>v{v.version}</b>
                <span class="status {v.status}">{v.status}</span>
              </span>
              <span class="reason">{v.reason.text}</span>
              <span class="sub">
                {v.gateReport ? `gate ${v.gateReport.passed}/${v.gateReport.total}` : "not gated"}
                {#if v.createdBy} · {v.createdBy}{/if}
              </span>
            </button>
          </li>
        {/each}
      </ol>

      <div class="detail">
        <div class="card fields">
          <span class="label">Fields read</span>
          <span class="chips">{#each current.fieldsUsed || [] as f}<span>{f}</span>{/each}</span>
        </div>

        {#if current.params && Object.keys(current.params).length}
          <div class="card params">
            <span class="label">Parameters the cheap model fills</span>
            {#each Object.entries(current.params) as [name, spec]}
              <div class="param">
                <b>{name}</b>
                <span class="ty">{spec.type || "string"}{spec.optional ? " · optional" : ""}</span>
                <span class="desc">{spec.description || ""}</span>
                {#if spec.values}<span class="vals">{spec.values.join(" · ")}</span>{/if}
              </div>
            {/each}
          </div>
        {/if}

        <GateTests skill={current} />

        {#if prev}
          <TemplateDiff before={prev.templateJson} after={current.templateJson} />
        {:else}
          <div class="card tpl">
            <div class="h">pipeline template</div>
            {#each stagesOf(current.templateJson) as line, i}
              <div class="ln"><span>{i + 1}</span><span>{line}</span></div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .page { display: flex; flex-direction: column; gap: 16px; overflow-y: auto; min-height: 0; }
  .idle { padding: 56px 28px; text-align: center; }
  .idle h2 { margin: 0 0 8px; font-size: 20px; }
  .idle p { margin: 0; color: var(--muted); }
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
  h1 { margin: 0; font: 600 20px var(--mono); letter-spacing: -.01em; overflow-wrap: break-word; }
  .intent { margin: 4px 0 0; font-size: 13px; color: var(--muted); line-height: 1.5; max-width: 60ch; }
  .meta { display: flex; gap: 22px; flex-shrink: 0; }
  .meta div { display: flex; flex-direction: column; align-items: flex-end; }
  .meta span { font-size: 11px; letter-spacing: .08em; color: var(--muted); text-transform: uppercase; }
  .meta b { font: 600 18px var(--mono); }
  .grid { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; align-items: start; }
  .timeline { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
  .timeline li { position: relative; padding-left: 18px; }
  .timeline li::before { content: ""; position: absolute; left: 5px; top: 0; bottom: 0; width: 2px; background: var(--line); }
  .timeline li:first-child::before { top: 18px; }
  .timeline li:last-child::before { bottom: calc(100% - 18px); }
  .timeline li::after { content: ""; position: absolute; left: 0; top: 14px; width: 12px; height: 12px;
                        border-radius: 50%; background: var(--panel); border: 2px solid var(--faint); }
  .v { display: block; width: 100%; text-align: left; margin-bottom: 8px; background: var(--panel);
       border: 1px solid var(--line); border-radius: var(--r); padding: 10px 12px; cursor: pointer; font: inherit; }
  .v.on { border-color: var(--ink); box-shadow: 0 0 0 1px var(--ink); }
  .top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .top b { font: 600 13px var(--mono); }
  .status { font: 600 10.5px var(--mono); padding: 2px 8px; border-radius: 999px; }
  .status.promoted { background: var(--cheap-bg); color: var(--green-ink); }
  .status.flagged { background: var(--mid-bg); color: var(--mid); }
  .status.rejected { background: var(--bad-bg); color: #8A1C12; }
  .status.retired, .status.candidate { background: var(--line-2); color: var(--muted); }
  .reason { display: block; font-size: 12.5px; line-height: 1.45; margin-top: 5px; color: var(--ink-2); }
  .sub { display: block; font: 11px var(--mono); color: var(--muted); margin-top: 4px; }
  .detail { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); }
  .fields { padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; font: 11.5px var(--mono); }
  .chips span { padding: 2px 7px; border-radius: 4px; background: var(--line-2); }
  .params { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
  .param { display: grid; grid-template-columns: 130px 130px minmax(0, 1fr); gap: 8px; font-size: 12.5px; align-items: baseline; }
  .param b { font: 500 12.5px var(--mono); }
  .ty { font: 11.5px var(--mono); color: var(--muted); }
  .desc { color: var(--ink-2); line-height: 1.45; }
  .vals { grid-column: 3; font: 11.5px var(--mono); color: var(--muted); }
  .tpl { font: 12px var(--mono); overflow-x: auto; }
  .tpl .h { padding: 8px 12px; background: var(--bg); border-bottom: 1px solid var(--line);
            font: 12px var(--sans); color: var(--muted); border-radius: var(--r) var(--r) 0 0; }
  .tpl .ln { display: grid; grid-template-columns: 42px minmax(0, 1fr); padding: 3px 12px;
             color: var(--muted); white-space: pre-wrap; overflow-wrap: anywhere; }
  @media (max-width: 1180px) { .grid { grid-template-columns: minmax(0, 1fr); } .param { grid-template-columns: minmax(0, 1fr); } }
</style>
