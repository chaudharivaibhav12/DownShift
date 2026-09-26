"""Three question families over sample_supplies.sales.

Each family has:
  - a hand-written reference pipeline (the ground truth),
  - phrasing templates,
  - a parameter picker that draws values from the live data so every question has a real answer.

Expected answers are stored canonically as rows of {label, value}.
"""
import calendar
import random
from datetime import datetime, timedelta, timezone

from bson import Decimal128

MONTHS = list(calendar.month_name)[1:]


def _utc(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc)


def _num(v):
    if isinstance(v, Decimal128):
        return float(v.to_decimal())
    return float(v)


# ---------------------------------------------------------------- family 1

def f1_pipeline(p):
    return [
        {"$match": {"saleDate": {"$gte": p["start"], "$lt": p["end"]}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$storeLocation",
                    "revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}}},
        {"$sort": {"revenue": -1, "_id": 1}},
        {"$limit": p["limit"]},
    ]


def f1_rows(result):
    return [{"label": r["_id"], "value": round(_num(r["revenue"]), 2)} for r in result]


F1_TEMPLATES = [
    "What were the top {limit} stores by revenue in {period}?",
    "Rank the {limit} highest-grossing store locations for {period}.",
    "Which {limit} stores brought in the most sales revenue in {period}?",
    "Show me the best {limit} stores by total revenue during {period}.",
    "Top {limit} store locations by revenue, {period}?",
    "List the {limit} stores with the highest revenue (price times quantity) in {period}.",
    "For {period}, which stores had the biggest revenue? Give me the top {limit}.",
    "I need the {limit} best performing stores by sales dollars for {period}.",
    "Which store locations earned the most in {period}? Top {limit} please.",
    "Revenue leaderboard of stores for {period}: top {limit}.",
]


def f1_params(rng, ctx, i):
    year = rng.choice(ctx["years"])
    kind = i % 3
    if kind == 0:  # a month
        m = rng.randint(1, 12)
        start = _utc(year, m)
        end = _utc(year + (m == 12), (m % 12) + 1)
        period = f"{MONTHS[m - 1]} {year}"
    elif kind == 1:  # a quarter
        q = rng.randint(1, 4)
        start = _utc(year, 3 * (q - 1) + 1)
        end = _utc(year + (q == 4), (3 * q) % 12 + 1)
        period = f"Q{q} {year}"
    else:  # a whole year
        start, end = _utc(year), _utc(year + 1)
        period = str(year)
    return {"start": start, "end": end, "limit": rng.choice([3, 3, 5]), "period": period}


# ---------------------------------------------------------------- family 2

def f2_pipeline(p):
    return [
        {"$match": {"storeLocation": p["store"]}},
        {"$unwind": "$items"},
        {"$match": {"items.tags": p["tag"]}},
        {"$group": {"_id": "$items.name", "units": {"$sum": "$items.quantity"}}},
        {"$sort": {"units": -1, "_id": 1}},
        {"$limit": p["limit"] + 1},  # one extra row so we can reject ties at the cut-off
    ]


def f2_rows(result):
    return [{"label": r["_id"], "value": _num(r["units"])} for r in result]


F2_TEMPLATES = [
    "In {store}, what are the top {limit} items tagged '{tag}' by units sold?",
    "Which {limit} '{tag}' products sold the most units at the {store} store?",
    "Best-selling {tag} items in {store}: top {limit} by quantity.",
    "At our {store} location, list the {limit} items with the tag {tag} that moved the most units.",
    "Top {limit} {tag} products by quantity sold in {store}?",
    "What {tag}-tagged items sold best in {store}? Give the top {limit} by units.",
    "Show the {limit} highest-volume items carrying the '{tag}' tag for the {store} store.",
    "For {store}, rank items tagged {tag} by total quantity sold and give me the top {limit}.",
    "Which items tagged '{tag}' had the most units sold in {store}? Top {limit}.",
    "{store} store, '{tag}' items: top {limit} by units sold.",
]


def f2_params(rng, ctx, i):
    return {"store": rng.choice(ctx["stores"]), "tag": rng.choice(ctx["tags"]), "limit": rng.choice([3, 5])}


# ---------------------------------------------------------------- family 3

def f3_pipeline(p):
    match = {"saleDate": {"$gte": _utc(p["year"]), "$lt": _utc(p["year"] + 1)}}
    if p.get("store"):
        match["storeLocation"] = p["store"]
    return [
        {"$match": match},
        {"$group": {"_id": "$purchaseMethod", "rate": {"$avg": {"$cond": ["$couponUsed", 1, 0]}}}},
        {"$sort": {"_id": 1}},
    ]


def f3_rows(result):
    return [{"label": r["_id"], "value": round(_num(r["rate"]), 4)} for r in result]


F3_TEMPLATES = [
    "For {scope} in {year}, what share of orders used a coupon, broken down by purchase method?",
    "Coupon usage rate by purchase method for {scope}, {year}?",
    "In {year}, for {scope}, what share of orders used a coupon, split by how the purchase was made?",
    "By purchase method, what fraction of {year} sales used a coupon ({scope})?",
    "Show coupon redemption rate per purchase method in {year} for {scope}.",
    "What percentage of orders used coupons in {year}, per purchase method, for {scope}?",
    "In {year}, for {scope}: coupon use rate by purchase method.",
    "Break down the coupon usage rate (share of orders with a coupon) by purchase method for {scope} during {year}.",
    "Which purchase methods saw the most coupon use in {year} ({scope})? Give the rate for each.",
    "{year}, {scope}: share of purchases with a coupon, by purchase method.",
]


def f3_params(rng, ctx, i):
    store = rng.choice(ctx["stores"]) if i % 2 else None
    return {"year": rng.choice(ctx["years"]), "store": store,
            "scope": f"the {store} store" if store else "all stores"}


# Held-out wordings for an honest validation run (E14). Never tune prompts or guardrails against these.
FRESH_TEMPLATES = {
    "top_stores_by_revenue": [
        "Which {limit} shops made the most money in {period}?",
        "Give me the {limit} top-earning locations for {period}, ranked.",
        "{period}: who were our {limit} biggest stores by revenue?",
        "Can you rank stores by gross revenue for {period} and keep the top {limit}?",
        "Top-{limit} revenue stores in {period}, please.",
        "Across all locations, which {limit} generated the highest revenue in {period}?",
        "I'd like the {limit} highest-revenue stores for {period}.",
        "What are the {limit} best stores by money taken in during {period}?",
        "Store revenue ranking for {period} - show the top {limit}.",
        "Name the {limit} locations with the largest total sales value in {period}.",
    ],
    "top_items_by_tag_in_store": [
        "What {limit} '{tag}' items move the most units at {store}?",
        "{store}: which {tag} products sold in the highest quantities? Top {limit}.",
        "Most-sold '{tag}' items (by units) at the {store} store - give {limit}.",
        "Rank {tag}-tagged products at {store} by quantity and show {limit}.",
        "For the {store} shop, the {limit} '{tag}' items with the most units sold?",
        "Top {limit} by volume among items tagged {tag}, {store} location.",
        "Which items with tag '{tag}' sold the most pieces in {store}? I need {limit}.",
        "In the {store} store, list {limit} '{tag}' products ordered by units sold.",
        "Highest-quantity {tag} items at {store}: top {limit}.",
        "Units sold leaderboard for '{tag}' items in {store}, top {limit}.",
    ],
    "coupon_rate_by_purchase_method": [
        "How likely were orders to use a coupon in {year} for {scope}, per purchase channel?",
        "For {scope}, {year}: coupon rate by sales channel (in store / online / phone).",
        "What fraction of {year} purchases at {scope} had a coupon, by purchase method?",
        "Per purchase method, the share of coupon orders in {year} ({scope}).",
        "Coupon adoption by purchase method, {year}, {scope}?",
        "In {year}, what % of orders used a coupon for {scope}? Split it by how people bought.",
        "Compare coupon usage rates across purchase methods for {scope} in {year}.",
        "Share of transactions with coupons in {year} for {scope}, grouped by purchase method.",
        "{scope} in {year}: for each purchase method, how often was a coupon used (as a rate)?",
        "Break out the coupon-use rate by channel for {scope}, year {year}.",
    ],
}

FAMILIES = {
    "top_stores_by_revenue": {"pipeline": f1_pipeline, "rows": f1_rows, "templates": F1_TEMPLATES,
                              "params": f1_params, "ordered": True, "rate": False},
    "top_items_by_tag_in_store": {"pipeline": f2_pipeline, "rows": f2_rows, "templates": F2_TEMPLATES,
                                  "params": f2_params, "ordered": True, "rate": False},
    "coupon_rate_by_purchase_method": {"pipeline": f3_pipeline, "rows": f3_rows, "templates": F3_TEMPLATES,
                                       "params": f3_params, "ordered": False, "rate": True},
}

# Params that are phrasing-only (not part of the query itself)
_DISPLAY_KEYS = {"period", "scope"}


def data_context(coll) -> dict:
    """Values that exist in the data: years, stores, item tags."""
    years = sorted(d["_id"] for d in coll.aggregate([
        {"$group": {"_id": {"$year": "$saleDate"}}}]) if d["_id"])
    stores = sorted(coll.distinct("storeLocation"))
    tags = sorted(coll.distinct("items.tags"))
    return {"years": years, "stores": stores, "tags": tags}


def build_cases(coll, per_family: int = 10, holdout_every: int = 3, seed: int = 42, fresh: bool = False) -> list[dict]:
    """Generate questions with expected answers computed by the reference pipelines.
    fresh=True uses FRESH_TEMPLATES (held-out wordings) instead of the tuning set."""
    rng = random.Random(seed)
    ctx = data_context(coll)
    if not (ctx["years"] and ctx["stores"] and ctx["tags"]):
        raise ValueError(f"data looks wrong: {ctx}")
    cases = []
    for fam, spec in FAMILIES.items():
        made, attempts, seen = 0, 0, set()
        while made < per_family and attempts < per_family * 50:
            attempts += 1
            p = spec["params"](rng, ctx, made)
            key = tuple(sorted((k, str(v)) for k, v in p.items() if k not in _DISPLAY_KEYS))
            if key in seen:
                continue
            seen.add(key)
            if fam == "top_items_by_tag_in_store":
                # fetch 6 rows, then use the largest top-N (asked N, else 3, else 2) whose cut-off isn't a tie
                rows = spec["rows"](list(coll.aggregate(spec["pipeline"]({**p, "limit": 5}))))
                ok = [n for n in (p["limit"], 3, 2)
                      if len(rows) > n and rows[n - 1]["value"] != rows[n]["value"]]
                if not ok:
                    continue
                p["limit"] = ok[0]
                rows = rows[: p["limit"]]
            else:
                rows = spec["rows"](list(coll.aggregate(spec["pipeline"](p))))
            if not rows:
                continue
            if fam == "top_stores_by_revenue" and len(rows) < p["limit"]:
                continue
            templates = FRESH_TEMPLATES[fam] if fresh else spec["templates"]
            question = templates[made % len(templates)].format(**p)
            query_params = {k: v for k, v in p.items() if k not in _DISPLAY_KEYS}
            cases.append({
                "caseId": f"{fam}-{made:02d}",
                "family": fam,
                "question": question,
                "params": query_params,
                "expectedRows": rows,
                "ordered": spec["ordered"],
                "rate": spec["rate"],
                "split": "holdout" if made % holdout_every == holdout_every - 1 else "gate",
            })
            made += 1
        if made < per_family:
            raise ValueError(f"only built {made} cases for {fam}; check the data")
    return cases
