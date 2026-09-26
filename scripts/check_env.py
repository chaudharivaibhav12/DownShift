"""Step 1 check: MongoDB reachable, sample data loaded, every model tier answers through OpenRouter.

Run:  python -m scripts.check_env
"""
from downshift import config, db, llm


def main():
    c = db.client()
    c.admin.command("ping")
    print("[mongo] ping ok")

    n = db.data_coll(c).estimated_document_count()
    print(f"[mongo] {config.DATA_DB}.{config.DATA_COLLECTION}: {n} documents")
    if n == 0:
        print("  -> Load the sample data: Atlas UI > your cluster > ... > Load Sample Dataset")

    for tier, model in config.MODELS.items():
        r = llm.chat(model, "Reply with one word.", "Say ok.", max_tokens=5)
        if r.error:
            print(f"[{tier:8}] {model}: ERROR {r.error}")
        else:
            print(f"[{tier:8}] {model} -> used {r.model}: '{r.text}' cost=${r.cost_usd:.6f} {r.latency_ms} ms")


if __name__ == "__main__":
    main()
