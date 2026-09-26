"""Downshift API + console.

Run:   uvicorn server.app:app --port 8000            (real Atlas + OpenRouter, after scripts.setup_db / build_benchmark)
       DOWNSHIFT_DEMO=1 uvicorn server.app:app --port 8000   (fully offline demo)
       DOWNSHIFT_MODELS=standin uvicorn server.app:app --port 8000   (real Atlas + scripted stand-in models)
Open:  http://localhost:8000
"""
import asyncio
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from bson import Decimal128, ObjectId, json_util
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from downshift import config, db, ledger, repair, schema, skills, trace
from downshift.watcher import SchemaWatcher
from downshift.answer import answer

DEMO = os.environ.get("DOWNSHIFT_DEMO") == "1"
STANDIN = not DEMO and os.environ.get("DOWNSHIFT_MODELS", "").lower() == "standin"
MODE = "demo" if DEMO else "standin" if STANDIN else "live"
demo = None
if DEMO or STANDIN:
    from downshift import demo as demo_mod
    demo = demo_mod.install(real_db=STANDIN)

app = FastAPI(title="Downshift")
WEB = Path(__file__).resolve().parent.parent / "web"
ENGINE = threading.Lock()          # one engine operation at a time
JOB = {"name": None, "done": 0, "total": 0}
SUPPRESS = {"until": 0.0}  # the button renames data itself; the change-stream watcher must not repair it twice
WATCHER = None


def _adb():
    return db.app_db(db.client())


def _data():
    return db.data_coll(db.client())


def _plain(x):
    """Decimal128 (Atlas stores sample_supplies prices this way) -> float, recursively. Also fixes answers that were
    stored earlier with {"$numberDecimal": "..."} wrappers."""
    if isinstance(x, Decimal128):
        return float(x.to_decimal())
    if isinstance(x, dict):
        if len(x) == 1 and "$numberDecimal" in x:
            return float(x["$numberDecimal"])
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return x


def _clean(doc):
    """Mongo document -> JSON-safe dict."""
    return json.loads(json_util.dumps(_plain(doc), json_options=json_util.RELAXED_JSON_OPTIONS))


def _schema_text():
    snap = schema.latest(_adb().schema_registry, config.DATA_COLLECTION)
    if not snap:
        raise HTTPException(503, "No schema snapshot. Run python -m scripts.setup_db first.")
    return schema.schema_for_prompt(snap["fields"])


def _ask(question: str, source: str = "ask") -> dict:
    adb = _adb()
    with trace.collect() as steps:
        t0 = time.perf_counter()
        r = answer(adb, _data(), question, _schema_text())
        total_ms = (time.perf_counter() - t0) * 1000
    rows = r["rows"] or []
    rec = {
        "ts": datetime.now(timezone.utc), "question": question, "source": source, "path": r["path"],
        "cost": round(r["cost"], 6), "ms": round(total_ms), "skill": r["skill"], "params": r.get("params"),
        "steps": steps, "rowCount": len(rows), "rows": _clean(rows[:10]), "trace": r["trace"],
    }
    rec["_id"] = adb.answers.insert_one(dict(rec)).inserted_id
    ledger.event(adb, "answered", path=r["path"], skill=r["skill"], cost=rec["cost"], ms=rec["ms"])
    return _clean(rec)


# ------------------------------------------------------------------ requests

class AskIn(BaseModel):
    question: str


class SchemaIn(BaseModel):
    old: str | None = None
    new: str | None = None


@app.post("/api/ask")
def ask(body: AskIn):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Type a question first.")
    if not ENGINE.acquire(timeout=60):
        raise HTTPException(409, "Downshift is busy with another operation. Try again in a moment.")
    try:
        return _ask(q)
    finally:
        ENGINE.release()


def _run_job(name, fn):
    if JOB["name"]:
        raise HTTPException(409, f"Already running: {JOB['name']}.")
    JOB.update(name=name, done=0, total=0)

    def worker():
        try:
            with ENGINE:
                fn()
        finally:
            JOB.update(name=None)

    threading.Thread(target=worker, daemon=True).start()
    return {"started": name}


@app.post("/api/replay")
def replay():
    cases = list(_adb().test_cases.find({}, {"question": 1, "_id": 0}).sort("caseId", 1))
    if not cases:
        raise HTTPException(503, "No benchmark questions. Run python -m scripts.build_benchmark first.")

    def fn():
        JOB["total"] = len(cases)
        for c in cases:
            _ask(c["question"], source="replay")
            JOB["done"] += 1
    return _run_job("replay", fn)


@app.post("/api/schema-change")
def schema_change(body: SchemaIn):
    data = _data()
    if body.old and body.new:
        old, new = body.old, body.new
    else:  # toggle the demo field
        has_old = data.count_documents({"storeLocation": {"$exists": True}}, limit=1)
        old, new = ("storeLocation", "store_location") if has_old else ("store_location", "storeLocation")

    def fn():
        SUPPRESS["until"] = time.time() + 3600
        try:
            res = data.update_many({old: {"$exists": True}}, {"$rename": {old: new}})
            ledger.event(_adb(), "documents_changed", renamed=[old, new], count=res.modified_count, source="button")
            repair.handle_schema_change(_adb(), data)
        finally:
            SUPPRESS["until"] = time.time() + 10   # let the watcher's echo of our own rename settle and be dropped
    out = _run_job("schema-change", fn)
    out.update(old=old, new=new)
    return out


def _auto_repair(info: dict):
    """Called by the change-stream watcher when documents in the data collection changed shape."""
    if time.time() < SUPPRESS["until"]:
        print(f"[watch] ignoring our own rename ({info['count']} events)")
        return
    print(f"[watch] documents changed shape: removed {info['removed']} added {info['added']} ({info['count']} events)")
    with ENGINE:
        JOB.update(name="schema-change", done=0, total=0)
        try:
            adb = _adb()
            ledger.event(adb, "documents_changed", renamed=info.get("renamed") or [], count=info["count"],
                         removed=info["removed"], added=info["added"], source="change stream")
            r = repair.handle_schema_change(adb, _data())
            print(f"[watch] schema v{r['version']} changed {r['changed'] or 'nothing'}; "
                  f"repaired {sum(1 for x in r['repairs'] if x.get('ok'))}/{len(r['repairs'])}")
        finally:
            JOB.update(name=None)


@app.on_event("startup")
def _start_watcher():
    """Real database only (mongomock has no change streams). WATCH_SCHEMA=0 turns it off."""
    global WATCHER
    real_db = demo is None or getattr(demo, "real_db", False)
    if real_db and os.environ.get("WATCH_SCHEMA", "1") != "0":
        WATCHER = SchemaWatcher(_adb(), _data(), _auto_repair).start()


@app.post("/api/reset")
def reset():
    if demo is None:
        raise HTTPException(400, "Reset is only available in demo or stand-in mode.")
    if JOB["name"]:
        raise HTTPException(409, "Wait for the running operation to finish.")
    with ENGINE:
        demo.reset()
    return {"ok": True}


# ------------------------------------------------------------------ reads

def _frontier_cost_per_question(adb) -> float:
    """What a frontier-only system pays per question: the average cost of the frontier writing a pipeline."""
    base = list(adb.runs.find({"mode": "frontier"}, {"costUsd": 1}))
    if base:
        return sum(b["costUsd"] for b in base) / len(base)
    docs = list(adb.ledger.find({"path": "learn", "step": {"$exists": False}}, {"costUsd": 1}))
    if docs:
        return sum(d["costUsd"] for d in docs) / len(docs)
    # No measurement yet. The stand-in frontier costs exactly $0.02, so that is a real number in demo modes;
    # on a fresh live DB we don't invent one (UI shows "—" until a baseline or first learn exists).
    return 0.02 if demo is not None else None


@app.get("/api/state")
def state():
    adb = _adb()
    answers = list(adb.answers.find({}, {"rows": 0, "trace": 0}).sort("ts", 1))
    all_skills = list(adb.skills.find({}, {"gateTests": 0}).sort([("skillId", 1), ("version", 1)]))
    snap = schema.latest(adb.schema_registry, config.DATA_COLLECTION)
    repairs = list(adb.repairs.find().sort("ts", -1).limit(1))
    frontier_q = _frontier_cost_per_question(adb)
    spent = sum(a["cost"] for a in answers)
    last = answers[-10:]
    uses = {}
    for a in answers:
        if a.get("skill"):
            key = a["skill"].split(" ")[0]
            uses[key] = uses.get(key, 0) + 1
    for sk in all_skills:
        sk["uses"] = uses.get(f"{sk['skillId']}@v{sk['version']}", 0)
    return _clean({
        "demo": demo is not None,
        "mode": MODE,
        "watcher": WATCHER.status if WATCHER else "off",
        "job": dict(JOB),
        "stats": {
            "answers": len(answers),
            "skillsLive": sum(1 for s in all_skills if s["status"] == "promoted"),
            "flagged": sum(1 for s in all_skills if s["status"] == "flagged"),
            "spent": round(spent, 6),
            "costPerAnswer": round(sum(a["cost"] for a in last) / len(last), 6) if last else None,
            "frontierPerAnswer": round(frontier_q, 6) if frontier_q is not None else None,
            "paths": {p: sum(1 for a in answers if a["path"] == p) for p in ("cheap", "mid", "learn", "frontier")},
        },
        "counts": {"sales": _data().estimated_document_count(), "ledger": adb.ledger.count_documents({}),
                   "events": adb.events.estimated_document_count(), "skills": len(all_skills)},
        "race": [{"n": i + 1, "cost": a["cost"], "path": a["path"]} for i, a in enumerate(answers)],
        "answers": answers[-40:][::-1],
        "skills": all_skills,
        "schema": {"version": snap["version"] if snap else None, "fields": [f["path"] for f in snap["fields"]] if snap else []},
        "repair": repairs[0] if repairs else None,
        "events": list(adb.events.find().sort("ts", -1).limit(30)),
        "suggestions": [c["question"] for c in adb.test_cases.find({}, {"question": 1}).sort("caseId", 1).limit(30)][::3],
    })


@app.get("/api/answers/{answer_id}")
def get_answer(answer_id: str):
    doc = _adb().answers.find_one({"_id": ObjectId(answer_id)})
    if not doc:
        raise HTTPException(404, "No such answer.")
    return _clean(doc)


@app.get("/api/stream")
async def stream():
    """Server-sent events: a 'tick' whenever answers, events, skills or repairs change."""
    async def gen():
        last = None
        while True:
            adb = _adb()
            sig = (adb.answers.count_documents({}), adb.events.count_documents({}),
                   adb.skills.count_documents({}), JOB["name"], JOB["done"],
                   (adb.repairs.find_one(sort=[("ts", -1)]) or {}).get("stage"),
                   len((adb.repairs.find_one(sort=[("ts", -1)]) or {}).get("results", [])))
            if sig != last:
                last = sig
                yield f"data: {json.dumps({'type': 'tick'})}\n\n"
            await asyncio.sleep(0.4)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/flow")
def flow():
    return FileResponse(WEB / "flow.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
