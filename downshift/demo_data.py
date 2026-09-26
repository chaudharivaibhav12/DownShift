"""Synthetic sales data shaped like sample_supplies.sales, for offline tests."""
import random
from datetime import datetime, timedelta, timezone

STORES = ["Austin", "Denver", "London", "New York", "San Diego", "Seattle"]
ITEMS = {"pens": ["writing", "office", "school"], "notepad": ["office", "writing", "school"],
         "binder": ["school", "general", "organization"], "laptop": ["electronics", "school", "office"],
         "backpack": ["school", "travel", "kids"], "envelopes": ["stationary", "office", "general"],
         "printer paper": ["office", "stationary"]}
METHODS = ["In store", "Online", "Phone"]

def make_data(coll, n=3000, seed=1):
    r = random.Random(seed); base = datetime(2013, 1, 1, tzinfo=timezone.utc)
    docs = []
    for _ in range(n):
        names = r.sample(list(ITEMS), r.randint(1, 4))
        docs.append({"saleDate": base + timedelta(days=r.randint(0, 5 * 365 - 1), hours=r.randint(0, 23)),
                     "storeLocation": r.choice(STORES), "purchaseMethod": r.choice(METHODS),
                     "couponUsed": r.random() < 0.2,
                     "customer": {"age": r.randint(16, 75), "gender": r.choice("MF"), "satisfaction": r.randint(1, 5)},
                     "items": [{"name": nm, "tags": ITEMS[nm], "price": round(r.uniform(2, 900), 2),
                                "quantity": r.randint(1, 10)} for nm in names]})
    coll.insert_many(docs)

