<script>
  let { children } = $props();
</script>

<aside class="inspector">
  {@render children?.()}
</aside>

<style>
  .inspector { background: var(--panel); border-left: 1px solid var(--line); padding: 18px 20px;
               display: flex; flex-direction: column; gap: 12px; min-width: 0; overflow-y: auto; }
  @media (max-width: 1180px) { .inspector { display: none; } }
</style>
