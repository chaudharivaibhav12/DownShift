# Downshift

**A frontier model answers a new kind of data question once. Downshift turns that answer into a tested,
reusable skill, so a cheap model answers that kind of question from then on. When the database schema changes,
Downshift repairs the affected skills itself and proves the answers didn't change.**

Learn → Shift → Heal. Think of it as a JIT compiler for LLM analytics: you pay frontier prices once per *type* of
question, not once per question. Built on MongoDB Atlas (data, skill library, ledger, change streams) and
OpenRouter (model tiers).

## Results (real Atlas + OpenRouter, Sep 26 2026)

Data: Atlas `sample_supplies.sales` (5,000 orders). Benchmark: 30 questions, 3 families × 10 phrasings, answers
scored against hand-written reference pipelines. Models: cheap `llama-3.1-8b-instruct`, mid `gpt-4o-mini`,
frontier `claude-sonnet-4`, plus `openrouter/auto` for comparison.

**Baselines (no skills: each model writes the aggregation pipeline itself)**

| Model | Accuracy | Cost / question |
|---|---|---|
| cheap (Llama 3.1 8B) | 11/30 (37%) | $0.00002 |
| mid (GPT-4o-mini) | 22/30 (73%) | $0.00012 |
| frontier (Claude Sonnet 4) | 30/30 (100%) | $0.00408 |
| OpenRouter Auto | 29/30 (97%) | $0.00014 |

**Downshift (starting from zero skills, learning included)**

| Run | Accuracy | Cost / question | Paths |
|---|---|---|---|
| Tuning questions | 30/30 (100%) | $0.0023 | 27 cheap · 3 learn |
| **Held-out questions** (new wordings + new seed, never tuned on) | **30/30 (100%)** | **$0.0031** | 25 cheap · 1 mid · 4 learn |

Once a skill exists, an answer is one cheap-model call plus one Atlas aggregation: about **$0.00002 and < 1 s**,
roughly 100–200× cheaper than asking the frontier. The frontier cost is paid once per question type (~$0.02–0.03).

**Heal (real models):** renaming `storeLocation` → `store_location` on all 5,000 documents flagged 3/3 skills; the
frontier rewrote each template (one `$match` field); **21/21 stored test answers were identical** before and after;
all 3 re-passed the cheap-model gate. Cost **$0.015**, ~1 minute. Works in both directions, and it now triggers
**by itself** from an Atlas change stream when anything (Compass, mongosh, another app) renames the field.

Every experiment, what failed and what fixed it: `experiments/LOG.md` (local, gitignored).

## How it works

```
question ─► skill search ─► cheap model picks a skill + fills typed params ─► guardrails ─► Atlas aggregation ─► answer
                 │                         │ fails                                   
                 │                         ▼                                          
                 │                  mid model tries the same                          
                 │ no skill fits / mid fails                                          
                 ▼                                                                    
   LEARN: frontier writes a pipeline ─► answers ─► generalizes it into a skill (template + typed params + 12 tests)
          ─► self-check (reproduces its own answer) ─► promotion gate (cheap model must pass ≥ 85% of 8 tests)
          ─► promoted  │  rejected ─► reflect (frontier rewrites the descriptions) ─► re-gate on held-out tests
```

**Guardrails around the cheap model** (all deterministic code, applied both live and in the gate):

- **Typed params:** every value is validated against the skill's spec (type, allowed values, ranges).
- **Grounding:** a store / tag / method value must appear in the question as whole words, so no invented filters
  (catches "wrong skill picked" and hallucinated values).
- **Date check:** when a question names one clear period (a month, quarter, half or year), the filled
  `[start, end)` must match it exactly (8B models slip on date arithmetic; this sends the slip to mid).
- **Exclusive-end fix:** a month-end date given for an exclusive end bound becomes the next day.
- **"All" = no filter** for optional params; a param the skill doesn't have means the skill is too narrow → learn
  a wider one that replaces it.
- **Read-only pipelines:** `$out`, `$merge` and friends are refused; time and row limits on every query.

**Heal** (`downshift/repair.py`, `downshift/watcher.py`): a change stream on the data collection notices documents
changing shape, waits for the bulk update to settle, re-reads the schema, and flags every live skill whose
`fieldsUsed` touch a changed field (flagged = off the cheap path). The frontier rewrites each template; the new
template must reproduce the old answers exactly on every stored test; then the cheap-model gate runs again. Pass →
new version promoted, old one retired. Fail → the skill is marked `broken` (never served), the frontier answers
and learns fresh skills, and broken skills are retried on the next schema change (e.g. when the change is reverted).

**Ledger:** every model call (tier, model, tokens, cost, latency, outcome) goes to the time-series `ledger`
collection; lifecycle events (learned, promoted, rejected, reflected, flagged, repaired, broken) go to `events`,
which drives the console.

## Run it

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt
```

| Mode | Command | Needs |
|---|---|---|
| Offline demo | `$env:DOWNSHIFT_DEMO="1"; uvicorn server.app:app --port 8000` | nothing (mongomock + scripted models) |
| Hybrid | `$env:DOWNSHIFT_MODELS="standin"; uvicorn server.app:app --port 8000` | `MONGODB_URI` |
| **Live** | `uvicorn server.app:app --port 8000 --no-access-log` | `MONGODB_URI` + `OPENROUTER_API_KEY` |

Open http://localhost:8000 (console) and http://localhost:8000/flow (3D view). New PowerShell windows start
clean; to leave demo/hybrid mode in the same window: `Remove-Item Env:DOWNSHIFT_DEMO, Env:DOWNSHIFT_MODELS`.

**First-time live setup:** load the Atlas sample dataset (cluster → ⋯ → Load Sample Dataset), add your IP under
Network Access, copy `.env.example` to `.env` and fill it in, then:

```powershell
python -m scripts.check_env          # Mongo ping, 5,000 docs, one call per model tier with its cost
python -m scripts.setup_db           # downshift.* collections + indexes, schema snapshot
python -m scripts.build_benchmark    # 30 questions with expected answers (--fresh: held-out wordings)
```

**`.env` settings**

| Key | Meaning |
|---|---|
| `MONGODB_URI`, `OPENROUTER_API_KEY` | Atlas connection string; OpenRouter key |
| `CHEAP_MODEL`, `MID_MODEL`, `FRONTIER_MODEL`, `AUTO_MODEL` | OpenRouter model ids per tier (we use `meta-llama/llama-3.1-8b-instruct:nitro` for cheap) |
| `CHEAP_MAX_PRICE` | Price cap (USD / million tokens) for the cheap tier's provider, e.g. `0.05`: `:nitro` alone picked a 10× pricier provider |
| `PROVIDER_SORT` | `latency` / `throughput` / `price` for all named models (optional) |
| `GATE_PASS_RATE` | Share of gate tests the cheap model must pass (default 0.85) |
| `REFLECT_ON_REJECT` | `0` turns off reflection after a gate rejection |
| `WATCH_SCHEMA` | `0` turns off the change-stream watcher in the server |
| `DATA_DB`, `DATA_COLLECTION`, `APP_DB` | Defaults: `sample_supplies`, `sales`, `downshift` |

## The console

- **Live:** ask a question or *Replay 30 questions*. Each answer shows its execution path (frontier / mid / cheap),
  the system flow, the MongoDB collections it touched, a timed trace with costs, "frontier-only would pay", and
  the result rows. The cost chart compares Downshift with frontier-only as answers come in.
- **Repairs:** a schema change step by step: detected → flagged → frontier rewrites → answers verified → gate &
  promote, with the template diff and a before/after answer table. *Simulate schema change* toggles
  `storeLocation` ↔ `store_location`; renaming it anywhere else in Atlas does the same by itself.
- **Skills:** every skill version, status, fields read, gate score, uses, and repair/reflection lineage.
- **Flow** (`/flow`): a live 3D view: answers are particles running the frontier / mid / cheap lanes, skills are
  crystals that crack on a schema change and heal. **F** = full screen.

API: `POST /api/ask {question}`, `POST /api/replay`, `POST /api/schema-change {old?, new?}`, `POST /api/reset`
(demo/hybrid), `GET /api/state`, `GET /api/answers/{id}`, `GET /api/stream` (server-sent events).

## Scripts

| Command | What it does |
|---|---|
| `python -m scripts.run_baselines [--modes cheap,mid,frontier,auto]` | Each model writes pipelines itself; accuracy + cost table |
| `python -m scripts.run_downshift --reset-skills` | All 30 questions through Downshift from zero skills |
| `python -m scripts.ask "Top 3 stores by revenue in March 2016"` | One question, shows the path |
| `python -m scripts.inspect_skills [status]` | Skills with params, template, gate failures, held-out and dropped tests |
| `python -m scripts.show_answer "text"` | A stored console answer with its full trace |
| `python -m scripts.break_schema --rename storeLocation store_location` | Rename a field (the server's watcher repairs; `--repair-now` without a server) |
| `python -m scripts.watch_schema` | Standalone watcher (only when the server isn't running) |
| `python -m scripts.bench_latency` | Cheap-model latency and cost per OpenRouter provider option |

Results land in `results/` (gitignored). Tests: `python -m tests.offline_skill_engine`,
`python -m tests.offline_schema_repair`, `python -m tests.local_smoke` (offline, no keys; they write to a temp dir).

## Code map

| Path | What it does |
|---|---|
| `downshift/answer.py` | The answer loop: skill search → cheap → mid → learn |
| `downshift/learn.py` | Frontier write → generalize → self-check → tests (gate + held-out) → gate → reflect |
| `downshift/gate.py` | Promotion gate and the cheap-model select-and-fill call |
| `downshift/skills.py` | Skill documents, typed params, guardrails (grounding, dates, "all"), rendering, fields used |
| `downshift/periods.py` | Finds the one calendar period a question names (the date guardrail) |
| `downshift/repair.py` | Flag → rewrite → verify identical answers → re-gate; `broken` on failure |
| `downshift/watcher.py` | Change-stream watcher that triggers repair |
| `downshift/schema.py` | Schema inference (types, values, date ranges) and versioning in `schema_registry` |
| `downshift/prompts.py` | GENERALIZE, SELECT_AND_FILL, REPAIR, REFLECT |
| `downshift/llm.py`, `nl2mql.py` | OpenRouter calls with cost/latency; pipeline parsing, safety check, guarded run |
| `downshift/benchmark.py`, `scorer.py` | The 3 question families (tuning + held-out wordings) and scoring |
| `downshift/demo.py` | Offline demo / hybrid stand-in model |
| `server/app.py`, `web/` | FastAPI + SSE; the console and 3D view (plain HTML/CSS/JS, no build step) |

**Collections (`downshift` database):** `skills` (versioned: template, typed params, fieldsUsed, gate report,
gate + held-out tests), `test_cases`, `schema_registry`, `ledger` (time-series), `events` (TTL 1 day), `runs`,
`answers`, `repairs`.

## Known limits and next steps

- **Skill search is lexical** (word overlap). Fine for 3 question types; with many skills it needs **Atlas hybrid
  search** (Vector Search + Atlas Search fused with `$rankFusion`) on the `skills` collection, with a similarity
  threshold for "no skill fits". Next up, together with more question families.
- The gate checks that the cheap model can *use* a skill; correctness of the frontier's template is checked by the
  self-check, the benchmark's reference answers, and (on repair) identical-answer verification.
- One data collection and three question families so far; results above are single runs, not averages.
- Cheap-tier cost depends on the OpenRouter provider; `CHEAP_MAX_PRICE` keeps a speed preference from choosing a
  pricier one.
