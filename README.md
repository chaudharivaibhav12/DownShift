# Downshift

A frontier model solves a data question once; Downshift turns the answer into a tested skill so a cheap model can answer that kind of question from then on, and repairs the skill when the schema changes.

This repo covers **checkpoint 1 (baselines)** , **checkpoint 2 (the skill engine)** and **schema repair**. It sets up MongoDB, builds a 30-question benchmark with known answers, and measures how well each model tier answers with no skills. Those numbers are the "before" line on the cost chart.

## The console (works offline today)

```bash
pip install -r requirements.txt
DOWNSHIFT_DEMO=1 uvicorn server.app:app --port 8000     # macOS / Linux
```
```powershell
$env:DOWNSHIFT_DEMO="1"; uvicorn server.app:app --port 8000   # Windows PowerShell
```

Open http://localhost:8000 (first start takes ~10 s while it builds the demo data). Demo mode runs the real answer loop, gate, repair and ledger against an in-memory MongoDB (mongomock) and a scripted stand-in model, so every screen works without keys. Free-form questions are mapped to the nearest of the three question families.

- **Live**: ask a question or press *Replay 30 questions*. The first question of each kind is learned by the frontier (blue), later ones go to the cheap model (green); an occasional cheap slip escalates to mid (amber). Each answer shows its execution path, steps, trace, cost vs frontier-only, and result rows.
- **Repairs**: *Simulate schema change* renames `storeLocation` ↔ `store_location` in every sales document; you see skills flagged, rewritten, verified (answers identical) and re-gated.
- **Skills**: every skill version, its status, fields read, gate score and use count.
- **Flow** (`/flow`): a live 3D view of the same data (Three.js, vendored in `web/vendor/three`, no internet needed). Each answer is a particle that drops through skill search into the frontier, mid or cheap lane and lands on Atlas; skills are crystals in the library, cracking red on a schema change and turning green when repaired. The cost meter adds real costs as particles land. Press **F** for full screen (booth mode); *Orbit* toggles the slow camera sway (drag to look around). Screen-record this view for the video.
- *Reset* (demo only) starts over with fresh data.

With `.env` filled in (after the setup steps below), run `uvicorn server.app:app --port 8000` without `DOWNSHIFT_DEMO` and the same console runs on Atlas and OpenRouter.

**Hybrid mode (real Atlas, stand-in models).** With only `MONGODB_URI` set (no OpenRouter key yet), run
`$env:DOWNSHIFT_MODELS="standin"; uvicorn server.app:app --port 8000` (PowerShell). The console queries your real
Atlas data and does real schema renames; the models are the scripted stand-ins, so costs are illustrative. The badge
reads "Atlas · stand-in models". Reset wipes only the `downshift` app database and renames `store_location` back to
`storeLocation`; restarting the server keeps what's there. In PowerShell, clear the variable with
`Remove-Item Env:DOWNSHIFT_MODELS` before a fully real run.

API: `POST /api/ask {question}`, `POST /api/replay`, `POST /api/schema-change {old?, new?}`, `POST /api/reset`, `GET /api/state`, `GET /api/answers/{id}`, `GET /api/stream` (server-sent events).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in MONGODB_URI, OPENROUTER_API_KEY, model ids
```

In Atlas, load the sample dataset (cluster → ⋯ → Load Sample Dataset) so `sample_supplies.sales` exists, and add your IP under Network Access.

## Checkpoint 1 in four commands

```bash
python -m scripts.check_env          # Mongo ping, sample data count, one call per model tier with its cost
python -m scripts.setup_db           # creates downshift.* collections + indexes, snapshots the schema
python -m scripts.build_benchmark --show   # 30 questions (3 families x 10), expected answers, gate/holdout split
python -m scripts.run_baselines      # cheap, frontier, openrouter/auto over all 30; logs to downshift.ledger
```

Try a small run first: `python -m scripts.run_baselines --modes cheap --limit 5`.

**Checkpoint 1 is done when** the summary table shows each tier's accuracy and cost, and the cheap model fails often enough to matter (roughly under 70% while frontier is near 100%). If the cheap model already aces a family, swap in a smaller cheap model or a harder family before building skills.

## What's where

| Path | What it does |
|---|---|
| `downshift/config.py` | Environment, model ids per tier, safety limits |
| `downshift/db.py` | Mongo client and collections |
| `downshift/llm.py` | OpenRouter calls with cost, tokens and latency; JSON extraction |
| `downshift/schema.py` | Infers the data schema, versions it in `schema_registry` (used later for repair) |
| `downshift/benchmark.py` | The 3 question families: reference pipelines, phrasings, parameter picking |
| `downshift/scorer.py` | Compares any result to the expected rows, ignoring field names |
| `downshift/nl2mql.py` | Question → pipeline prompt, parsing (Extended JSON dates), safety check, guarded run |
| `downshift/trace.py` | Per-answer step timings and costs shown in the console trace |
| `downshift/demo.py`, `demo_data.py` | Offline demo: mongomock + scripted stand-in model |
| `server/app.py` | FastAPI API + server-sent events; serves `web/` |
| `web/` | The console (plain HTML/CSS/JS, no build step); `flow.*` is the 3D view |
| `scripts/*` | The four commands above |
| `tests/local_smoke.py` | Offline test with mongomock and a stub model (`pip install mongomock`, then `python -m tests.local_smoke`) |

## Collections (database `downshift`)

- `test_cases`: question, family, params, expected rows, gate/holdout split
- `ledger`: one entry per model run (time-series): mode, model, tokens, cost, latency, pass/fail
- `runs`: full detail per run: generated pipeline, raw model output, result preview, failure reason
- `schema_registry`: versioned schema of `sample_supplies.sales`
- `skills`, `events`: created now, used from checkpoint 2
- `answers`: every console answer with its steps (trace), params and first rows
- `repairs`: one document per schema change, updated stage by stage (detected → flagged → repairing → done)

## Question families

1. `top_stores_by_revenue`: top N stores by revenue (price × quantity) in a month, quarter or year
2. `top_items_by_tag_in_store`: top N items with a tag in one store, by units sold
3. `coupon_rate_by_purchase_method`: share of orders using a coupon per purchase method, for a year, optionally one store

## Checkpoint 2: the skill engine

```bash
python -m scripts.run_downshift --reset-skills   # all 30 questions through Downshift, starting with no skills
python -m scripts.ask "Top 3 stores by revenue in March 2016"   # one question, shows which path answered
```

How a question is answered (`downshift/answer.py`):

1. **Shortlist** promoted skills by word overlap with their intent and examples (Atlas hybrid search replaces this once the cluster is up).
2. **Cheap path:** the cheap model picks a skill and fills its parameters. Parameters are type-checked (`skills.validate_params`), substituted as typed values, safety-checked and run.
3. **Escalation:** bad parameters, an error or an empty result → the mid model tries the same.
4. **Learn path** (`downshift/learn.py`), when no skill fits or mid fails: the frontier model answers with a concrete pipeline, then generalizes it into a template with typed parameters and 8 test questions. The template must reproduce the original answer exactly (self-check).
5. **Gate** (`downshift/gate.py`): the cheap model must answer at least `GATE_PASS_RATE` (default 85%) of the test questions correctly with the skill. Pass → `promoted` (the previous version is `retired`). Fail → `rejected`, then:
6. **Reflect** (`learn.reflect`): the frontier model reads the gate's winning and losing traces side by side, finds the pattern (an omitted param, an inclusive/exclusive bound, a phrasing) and rewrites only the cheap-facing part of the skill: intent, param descriptions, examples. The template and the param contract (names, types, optional, values) stay fixed. The new version is re-gated once. This is contrastive reflection in the Strands [Harness Optimizer](https://strandsagents.com/blog/introducing-harness-optimizer/) sense: the skill is the tunable harness component, the gate is the reward, the traces in `ledger`/`runs` are the rollouts. Event: `skill_reflected`. `REFLECT_ON_REJECT=0` disables it.

Every model call is logged to `ledger` with its path (`cheap`, `mid`, `learn`, `gate`), and skill lifecycle events go to `events` for the console.

| New file | What it does |
|---|---|
| `downshift/skills.py` | Skill documents, typed params, template substitution (optional params drop their filter), fields-used extraction, promote/reject |
| `downshift/prompts.py` | The generalize and select-and-fill prompts |
| `downshift/learn.py` | Learn path: answer, generalize, self-check, tests, gate |
| `downshift/gate.py` | Promotion gate and the cheap-model select-and-fill call |
| `downshift/answer.py` | The answer loop with escalation |
| `downshift/ledger.py` | Ledger and event logging |
| `tests/offline_skill_engine.py` | Offline end-to-end test with a scripted stand-in model (`python -m tests.offline_skill_engine`) |

Known limit: a skill's test answers come from its own template, so the gate checks that the cheap model can *use* the skill, not that the frontier's template is right. The benchmark's held-out questions (scored against hand-written pipelines) are what check correctness.

## Schema repair

```bash
python -m scripts.watch_schema                                          # terminal 1: change stream on the sales data
python -m scripts.break_schema --rename storeLocation store_location   # terminal 2: the demo moment
python -m scripts.break_schema --rename store_location storeLocation   # undo (repairs back)
```

No watcher running? Add `--repair-now` to `break_schema`.

What happens (`downshift/repair.py`):

1. The watcher sees updates that add or remove fields, waits 3 s for the bulk update to finish, and re-reads the schema. `schema_registry` records the new version and `changedFields` (for a rename: both the old and the new name).
2. Every promoted skill whose `fieldsUsed` touches a changed field is **flagged**. Flagged skills are off the cheap path.
3. For each flagged skill the frontier model rewrites the template for the new schema (same params, same output shape).
4. **Verify:** with each stored test's params, the new template must give exactly the answers the old skill gave. A rename changes shape, not data, so any difference means the repair is wrong and it is refused.
5. **Gate:** the cheap model must pass the tests again. Pass → promoted as a new version, the flagged one retired.

While a skill is flagged, questions it would answer go to the frontier model (path `frontier`) without learning a duplicate skill. So users get slower answers, never wrong ones. Events: `schema_changed`, `skill_flagged`, `skill_repaired`, `repair_failed`.

Offline test: `python -m tests.offline_schema_repair`. It learns 3 skills, renames `storeLocation`, checks that all 3 are repaired to new versions, and that the benchmark then runs on the cheap path with no re-learning. It also checks that a bad repair is refused and answers fall back to the frontier.
