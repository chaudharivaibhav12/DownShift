"""Demo mode: run Downshift fully offline with an in-memory database and a scripted stand-in model.

Turn on with DOWNSHIFT_DEMO=1. Hybrid mode (DOWNSHIFT_MODELS=standin, no DOWNSHIFT_DEMO) uses the same stand-in
model but your real MongoDB from MONGODB_URI, so the console runs on real Atlas data before an OpenRouter key exists.
Everything else (answer loop, gate, repair, ledger, console) is the real code;
only MongoDB (mongomock) and the model calls (scripted) are stand-ins. Free-form questions are mapped to the
closest benchmark question, so the demo only knows the three question families.
"""
import random
import re
import threading
import time

from bson import json_util

from . import benchmark, config, db, llm, nl2mql, schema
from .demo_data import make_data

LATENCY = {"cheap": 0.25, "mid": 0.5, "frontier": 0.9, "auto": 0.6}
COST = {"frontier": 0.02, "mid": 0.002, "cheap": 0.0002, "auto": 0.01}
SLIP_EVERY = 9  # every 9th cheap fill forgets a param, so escalation to mid shows up in a replay
WEAK_FAMILY = "top_items_by_tag_in_store"  # its v1 description is too thin: the cheap model drops `tag` in 3 of 8 gate
                                           # questions until the frontier reflects and rewrites the description

TEMPLATES = {
    "top_stores_by_revenue": ([
        {"$match": {"saleDate": {"$gte": "{{start}}", "$lt": "{{end}}"}}}, {"$unwind": "$items"},
        {"$group": {"_id": "$storeLocation", "revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}}},
        {"$sort": {"revenue": -1, "_id": 1}}, {"$limit": "{{limit}}"}],
        {"start": {"type": "date", "description": "first day, inclusive"},
         "end": {"type": "date", "description": "day after the period, exclusive"},
         "limit": {"type": "int", "description": "how many stores", "min": 1, "max": 50}}),
    "top_items_by_tag_in_store": ([
        {"$match": {"storeLocation": "{{store}}"}}, {"$unwind": "$items"}, {"$match": {"items.tags": "{{tag}}"}},
        {"$group": {"_id": "$items.name", "units": {"$sum": "$items.quantity"}}}, {"$sort": {"units": -1, "_id": 1}},
        {"$limit": "{{limit}}"}],
        {"store": {"type": "string", "description": "store location"},
         "tag": {"type": "string", "description": "item tag"},
         "limit": {"type": "int", "description": "how many items"}}),
    "coupon_rate_by_purchase_method": ([
        {"$match": {"saleDate": {"$gte": "{{start}}", "$lt": "{{end}}"}, "storeLocation": "{{store}}"}},
        {"$group": {"_id": "$purchaseMethod", "rate": {"$avg": {"$cond": ["$couponUsed", 1, 0]}}}},
        {"$sort": {"_id": 1}}],
        {"start": {"type": "date", "description": "Jan 1 of the year, inclusive"},
         "end": {"type": "date", "description": "Jan 1 of next year, exclusive"},
         "store": {"type": "string", "optional": True, "description": "store location; omit for all stores"}}),
}
STORE_FIELDS = ("storeLocation", "store_location")
APP_COLLECTIONS = ("skills", "test_cases", "schema_registry", "events", "runs", "ledger", "repairs", "answers")


class Demo:
    def __init__(self, real_db: bool = False):
        self.real_db = real_db
        if real_db:
            self.client = db.client()          # real MongoDB from MONGODB_URI
        else:
            import mongomock
            self.client = mongomock.MongoClient()
        self.lock = threading.RLock()
        self.rng = random.Random(7)
        self.reg: dict[str, tuple[str, dict]] = {}
        self.cases: list[dict] = []
        self.fixed: dict[str, tuple[str, dict]] = {}   # skill test question -> (family, skill params); survives restarts
        self.fills = 0
        self.gate_calls = 0
        self.reflected: set[str] = set()

    # --------------------------------------------------------------- setup
    def install(self):
        if not self.real_db:
            db.client = lambda: self.client
        llm.chat = self.chat
        nl2mql.llm.chat = self.chat
        adb = db.app_db(self.client)
        if self.real_db and adb.test_cases.count_documents({}) and adb.schema_registry.count_documents({}):
            self._load()      # real DB: keep what's there across server restarts; Reset wipes it
        else:
            self.reset()

    def _load(self):
        data, adb = db.data_coll(self.client), db.app_db(self.client)
        self.cases = list(adb.test_cases.find({}, {"_id": 0}).sort("caseId", 1))
        self.fills = 0
        self.reg = {c["question"]: (c["family"], dict(c["params"])) for c in self.cases}
        self.ctx = benchmark.data_context(data)
        # Test questions the stand-in invented for existing skills live in each skill's gateTests; reload them so a
        # server restart doesn't make the gate guess params for them.
        self.fixed = {}
        for sk in adb.skills.find({}, {"skillId": 1, "gateTests": 1}):
            for t in sk.get("gateTests") or []:
                self.fixed[t["question"]] = (sk["skillId"], dict(t.get("params") or {}))

    def reset(self):
        data, adb = db.data_coll(self.client), db.app_db(self.client)
        if self.real_db:
            # Real database: keep the sample data (only undo our own demo rename) and wipe Downshift's app DB.
            if data.count_documents({"store_location": {"$exists": True}}, limit=1):
                data.update_many({"store_location": {"$exists": True}}, {"$rename": {"store_location": "storeLocation"}})
            if data.estimated_document_count() == 0:
                raise SystemExit(f"{config.DATA_DB}.{config.DATA_COLLECTION} is empty: load the Atlas sample dataset first.")
            for name in APP_COLLECTIONS:
                adb.drop_collection(name)
            db.ensure_collections(adb)
        else:
            for name in self.client.list_database_names():
                self.client.drop_database(name)
            make_data(data)
            for name in APP_COLLECTIONS:
                adb.create_collection(name)
        schema.snapshot(adb.schema_registry, data, config.DATA_COLLECTION)
        self.cases = benchmark.build_cases(data)
        adb.test_cases.insert_many([dict(x) for x in self.cases])
        self.fills = 0
        self.fixed = {}
        self.gate_calls = 0
        self.reflected = set()
        self.reg = {c["question"]: (c["family"], dict(c["params"])) for c in self.cases}
        self.ctx = benchmark.data_context(data)

    # --------------------------------------------------------------- helpers
    def resolve(self, question: str):
        """Exact benchmark question, else the closest one by word overlap (demo only)."""
        if question in self.reg:
            return self.reg[question]
        words = set(re.findall(r"[a-z0-9]+", question.lower()))

        def score(q):  # shared words, numbers (years, limits) count triple
            common = words & set(re.findall(r"[a-z0-9]+", q.lower()))
            return sum(3 if w.isdigit() else 1 for w in common)
        best = max(self.reg, key=score)
        return self.reg[best]

    @staticmethod
    def _iso(d):
        return d.strftime("%Y-%m-%d")

    def skill_params(self, fam, p):
        if fam == "top_stores_by_revenue":
            return {"start": self._iso(p["start"]), "end": self._iso(p["end"]), "limit": p["limit"]}
        if fam == "top_items_by_tag_in_store":
            return {"store": p["store"], "tag": p["tag"], "limit": p["limit"]}
        out = {"start": f"{p['year']}-01-01", "end": f"{p['year'] + 1}-01-01"}
        if p.get("store"):
            out["store"] = p["store"]
        return out

    @staticmethod
    def _to_field(text: str, field: str) -> str:
        for f in STORE_FIELDS:
            text = text.replace(f'"${f}"', f'"${field}"').replace(f'"{f}"', f'"{field}"')
        return text

    @staticmethod
    def _current_store_field(schema_text: str) -> str:
        return "store_location" if re.search(r"^- store_location:", schema_text, re.M) else "storeLocation"

    # --------------------------------------------------------------- the stand-in model
    def chat(self, model, system, user, max_tokens=1500, retries=2):
        tier = next((k for k, v in config.MODELS.items() if v == model), "frontier")
        time.sleep(LATENCY[tier] * (0.8 + 0.4 * self.rng.random()))
        cost = COST[tier]

        def R(text):
            return llm.LLMResult(text=text, model=f"demo/{tier}", cost_usd=cost, tokens_in=400, tokens_out=150,
                                 latency_ms=int(LATENCY[tier] * 1000))

        if "TASK: REPAIR" in user:
            old = re.search(r"Old template \(Extended JSON.*?\n(.*?)\n\n(?:Write|Rewrite)", user, re.S).group(1)
            field = self._current_store_field(user.split("Current schema:")[1])
            fixed = self._to_field(old, field)
            return R('{"note": "store field is now ' + field + '", "template": ' + fixed + "}")

        if "TASK: REFLECT" in user:
            sid = re.search(r"^Skill: (.*)$", user, re.M).group(1)
            params = json_util.loads(re.search(r"^Params \(JSON\): (.*)$", user, re.M).group(1))
            self.reflected.add(sid)
            fixed = {k: {"description": v.get("description", "") + " Required: always read it from the question, even when the question leads with the store or the count."}
                     for k, v in params.items()}
            return R(json_util.dumps({"intent": f"Answer {sid.replace('_', ' ')} questions; every param is filled from the question",
                                      "params": fixed, "examples": [f"Best-selling office items in Austin: top 3", f"Top 5 stationary products sold at the Denver store"],
                                      "note": "losing traces all name the store before the tag; the cheap model dropped `tag`. Descriptions now say each param is required and where it appears."}))

        if "TASK: GENERALIZE" in user:
            q = re.search(r"^Question: (.*)$", user, re.M).group(1)
            fam, p = self.resolve(q)
            template, params = TEMPLATES[fam]
            field = self._current_store_field(user.split("Question:")[0])
            tests = []
            for i in range(8):
                tp = benchmark.FAMILIES[fam]["params"](self.rng, self.ctx, i)
                if fam == "top_items_by_tag_in_store":
                    tp["limit"] = 3
                tq = benchmark.FAMILIES[fam]["templates"][(i + 3) % 10].format(**tp) + f" (test {i + 1})"
                qp = {k: v for k, v in tp.items() if k not in ("period", "scope")}
                self.reg[tq] = (fam, qp)
                self.fixed[tq] = (fam, self.skill_params(fam, qp))
                tests.append({"question": tq, "params": self.skill_params(fam, qp)})
            obj = {"skillId": fam, "intent": f"Answer {fam.replace('_', ' ')} questions", "params": params,
                   "template": template, "originalParams": self.skill_params(fam, p), "testQuestions": tests}
            return R(self._to_field(json_util.dumps(obj), field))

        if "TASK: SELECT_AND_FILL" in system:
            if user in self.fixed:
                fam, sp = self.fixed[user][0], dict(self.fixed[user][1])
            else:
                fam, p = self.resolve(user)
                sp = self.skill_params(fam, p)
            if f"skillId: {fam}" not in system:
                return R('{"skillId": null}')
            if tier == "cheap":
                self.fills += 1
            if tier == "cheap" and self.fills % SLIP_EVERY == 5:
                sp = dict(sp)
                sp.pop(next(iter(sp)))
            if tier == "cheap" and fam == WEAK_FAMILY and fam not in self.reflected and "(test " in user:
                self.gate_calls += 1
                if self.gate_calls % 3 == 1:  # 3 of 8 gate questions -> 5/8, below the 85% bar
                    sp = {k: v for k, v in sp.items() if k != "tag"}
            return R(json_util.dumps({"skillId": fam, "params": sp}))

        # concrete pipeline, written against the current schema
        fam, p = self.resolve(user)
        pipe = benchmark.FAMILIES[fam]["pipeline"](dict(p))
        if fam == "top_items_by_tag_in_store":
            pipe[-1] = {"$limit": p["limit"]}
        return R(self._to_field(json_util.dumps({"pipeline": pipe}), self._current_store_field(system)))


_demo: Demo | None = None


def install(real_db: bool = False) -> Demo:
    global _demo
    if _demo is None:
        _demo = Demo(real_db)
        _demo.install()
    return _demo
