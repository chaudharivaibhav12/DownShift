<script>
  let { kind = "answer" } = $props();
  const copy = {
    answer: ["Pick a question", "Every answer shows which model handled it, what it cost, and why that path was taken."],
    skill: ["Pick a skill", "A skill is a tested pipeline template the cheap model can fill. Each one keeps its full version history."],
    repair: ["No repair selected", "A schema change flags every skill that reads a changed field, then the frontier model rewrites each one."],
    run: ["No run selected", "A run is one replay of the benchmark: which families went cheap, what it cost, how it compares to frontier-only."],
  };
</script>

<div class="empty">
  <h2>{copy[kind][0]}</h2>
  <p>{copy[kind][1]}</p>
</div>

<style>
  .empty { padding: 64px 32px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 10px; }
  h2 { margin: 0; font-size: 20px; font-weight: 600; }
  p { margin: 0; max-width: 520px; color: var(--muted); line-height: 1.6; }
</style>
