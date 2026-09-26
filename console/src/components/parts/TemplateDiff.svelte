<script>
  import { diffLines } from "../../lib/derive.js";
  let { before, after } = $props();
  let d = $derived(diffLines(before, after));
</script>

<div class="card diff">
  <div class="h">pipeline template · {d.changed} stage{d.changed === 1 ? "" : "s"} changed</div>
  {#each d.lines as l}
    <div class="ln {l.kind}">
      <span>{l.n}{l.kind === "del" ? " −" : l.kind === "add" ? " +" : ""}</span>
      <span>{l.text}</span>
    </div>
  {/each}
</div>

<style>
  .diff { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r);
          font: 12px var(--mono); overflow-x: auto; }
  .h { padding: 8px 12px; background: var(--bg); border-bottom: 1px solid var(--line);
       font: 12px var(--sans); color: var(--muted); border-radius: var(--r) var(--r) 0 0; }
  .ln { display: grid; grid-template-columns: 42px minmax(0, 1fr); padding: 3px 12px;
        color: var(--muted); white-space: pre-wrap; overflow-wrap: anywhere; }
  .ln.del { background: #FDECEA; color: #8A1C12; }
  .ln.add { background: #E6F4EC; color: #145C38; }
  .ln:last-child { padding-bottom: 8px; }
</style>
