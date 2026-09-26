# Downshift console: workbench revamp

Date: 2026-09-26
Status: approved design, implementation sequenced below

## Why

The console works but is hard to navigate. Four routes (Live, Repairs, Skills, Flow) are four
separate places with no shared spine: nothing carries a selected skill or answer from one to the
next. Confirmed pain points, from the person who uses it daily:

1. **Understanding what happened** — the "why this path" story is scattered across four panels.
2. **Inspecting skills** — a flat 7-column table with no filter, no grouping by family, and version
   lineage buried in parentheses. No way to see how a skill evolved v1 → v2 → v3, or read its
   template and gate tests.
3. **Comparing runs over time** — everything is "the currently selected answer". A 30-question
   replay cannot be viewed as a whole.
4. **Disconnected views** — no shared context between routes.

Intended outcome: someone opening this without a narrator understands what the system does, and it
reads as a real product rather than a hackathon console. No hard deadline.

## Shape: a workbench

Live / Repairs / Skills stop being routes and become *modes of one workspace*.

- **Header** — brand, live dot, demo tag, global actions (Replay, Simulate schema change). The four
  route tabs go away. `/flow` survives as a link; it is a separate full-screen medium and is not
  ported.
- **Left rail (~300px)** — the spine. Segmented control: Answers · Skills · Repairs · Runs, plus a
  text filter. Always present; this is how you navigate.
- **Centre workspace** — renders whatever is selected, by kind.
- **Right inspector (~330px)** — context for that same selection.

Selection is one piece of state: `{kind, id}`. That single cursor is what fixes disconnection.

### Cross-links

Every reference to an entity is clickable and moves the cursor without leaving the screen:

- an answer's skill chip → that skill, centre becomes its lineage
- a skill's "N answers" → rail filtered to those answers
- a repair job's skill → that skill, repaired version highlighted
- a gate failure → the answer that failed it

### Workspace by kind

| Selected | Centre |
|---|---|
| Answer | Verdict card, step flow, trace (ported as-is; already works) |
| Skill | **New** — version lineage with the reason for each version, template, per-test gate results |
| Repair | Stepper, template diff, equivalence table (ported) |
| Run | **New** — a replay batch as one entity: per-family path mix, cost vs frontier-only, accuracy |

## State and data flow

The server remains the single source of truth. The client never mutates state; SSE only invalidates.
No optimistic updates, no client-side model of the engine.

Stores:

| Store | Kind | Holds |
|---|---|---|
| `state` | writable | the `/api/state` payload, replaced wholesale on refresh |
| `selection` | writable | `{kind, id}` — the cursor |
| `connection` | writable | `'live' \| 'off'` — drives the live dot |
| `pending` | writable | the in-flight ask (`question`, `startedAt`) |

Everything else is derived: `answers`, `skills`, `repair`, `stats`, `events`, plus `lineage`
(skills grouped by `skillId`, ordered by version) and `selected` (the resolved entity).

**The lineage view needs no backend.** Every fact is already on the skill documents: `repairedFrom`,
`reflectedFrom`, `reflectionNote`, `status`, `gateReport`, `version`.

Two pieces of state stay client-local because the server does not know them:

1. **The pending ask** — elapsed timer and skeletons, so a 45s learn is not a frozen screen.
2. **`follow`** — auto-select the newest answer until the user explicitly picks one. This is why the
   demo runs hands-free; preserve it.

```
EventSource /api/stream ──tick──▶ debounced refresh() ──▶ GET /api/state ──▶ state store
                                         8s interval retained as the existing safety net
GET /api/answers/{id} ──▶ per-id detail cache (today's `full` Map, kept)
```

Selection is encoded in the URL (`/skill/top_stores_by_revenue`, `/answer/:id`, `/repair/:id`), so
skills and answers are deep-linkable. Start with ~30 lines of hash routing; add a router dependency
only if that hurts.

## Error handling

Unchanged in behaviour. A failed fetch flips `connection` to `off` so the live dot greys rather than
lying. Errors surface in the toast, which also writes to the single `role="status"` region. The
accessibility work already shipped — one live region, `aria-describedby` on the ask input, the
contrast-corrected tokens — ports into components rather than being rebuilt.

## Stack

Svelte + Vite. The app is already one global state object refreshed from `/api/state` and
invalidated by SSE ticks, which is a Svelte store almost line for line. No component library: the
bespoke palette and mono type are an asset and a library would fight them.

Two structural wins beyond reorganisation:

1. **`esc()` disappears.** Today's renderers build HTML strings and hand-escape ~40 interpolations.
   One missed `esc()` is an injection bug. Svelte escapes by default, so the category goes away.
2. **The scroll affordance becomes a `use:fade` action** instead of manual listeners plus a
   `scrollUpdaters` array flushed on every render.

## Files

```
web/                      untouched until the switch; /flow never touched
console/
  package.json
  vite.config.js          proxy /api -> :8000 · build.outDir = ../web/dist
  src/
    main.js
    App.svelte            shell: Header + Rail + Workspace + Inspector
    lib/      stores.js · api.js · router.js · derive.js · format.js · a11y.js
    components/
      Header · Rail · RailItem · Inspector
      workspace/  AnswerView · SkillView* · RepairView · RunView* · EmptyView
      parts/      VerdictCard · PathRail · StepFlow · Trace · CostStrip
                  SkillLineage* · GateTests* · TemplateDiff · StatusPill · Chips
    styles/   tokens.css (the corrected palette) · base.css
```

`*` = new; everything else ports code that already works.

## Serving

`server/app.py` serves `web/dist/index.html` when it exists, otherwise the current vanilla console.
`git clone && uvicorn` keeps working with no Node installed; the new UI appears once built. No build
artifacts in git. `/flow` continues to be served from `web/` so the vendored-Three.js offline
guarantee is unaffected.

## Testing

There are no UI tests today. Vitest covers the **pure derivations only**: `lineage()` grouping,
`vsFrontier()`, `triedTiers()`, and the formatting helpers. Those are where real bugs live and they
are trivial to test. Component-render tests are deliberately out of scope — nobody maintains them on
a project this size, and claiming coverage we do not have is worse than none.

The three Python suites (`local_smoke`, `offline_skill_engine`, `offline_schema_repair`) must keep
passing; they do not touch `web/`.

## Sequence

Ordered so nothing collides with concurrent backend work:

1. Scaffold, shell, stores, router — no Python touched
2. Port AnswerView + CostStrip — parity with today's Live view
3. Port RepairView
4. SkillView + lineage + gate tests — biggest new value, zero backend
5. RunView + `GET /api/runs`, `GET /api/runs/{batchId}` — the only step touching Python, last

Migration is non-destructive: if the work stalls, the switch is never flipped and nothing is broken.

## Risks

- **Two front-ends coexist during migration.** Mitigated by the fallback in `server/app.py` and by
  never editing `web/` after the port begins.
- **Step 5 touches `server/app.py`**, where concurrent backend work is happening. Sequenced last;
  the endpoints are additive and read-only.
- **`node_modules` enters the repo tree.** Added to `.gitignore` along with `web/dist`.
