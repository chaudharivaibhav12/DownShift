<script>
  import VerdictCard from "../parts/VerdictCard.svelte";
  import StepFlow from "../parts/StepFlow.svelte";
  import Trace from "../parts/Trace.svelte";
  import CostStrip from "../parts/CostStrip.svelte";
  let { answer } = $props();
</script>

<div class="col">
  <VerdictCard {answer} />
  <div class="canvas">
    <StepFlow {answer} />
    <Trace {answer} />
  </div>
  <CostStrip />
</div>

<style>
  .col { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 14px; }
  .canvas { flex: 1; min-height: 0; overflow: hidden; display: flex; gap: 18px; padding: 14px 18px;
            background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
            background-image: radial-gradient(#E6E9ED 1px, transparent 1px); background-size: 18px 18px; }
  @media (max-width: 1180px) { .canvas { flex-direction: column; } }
</style>
