import os

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"Missing environment variable {name}. Copy .env.example to .env and fill it in.")
    return val


MONGODB_URI = os.environ.get("MONGODB_URI", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

MODELS = {
    "cheap": os.environ.get("CHEAP_MODEL", "meta-llama/llama-3.1-8b-instruct"),
    "mid": os.environ.get("MID_MODEL", "openai/gpt-4o-mini"),
    "frontier": os.environ.get("FRONTIER_MODEL", "anthropic/claude-sonnet-4"),
    "auto": os.environ.get("AUTO_MODEL", "openrouter/auto"),
}

# OpenRouter provider routing for our named models: "latency" | "throughput" | "price" | "" (OpenRouter default).
# Not applied to openrouter/* routers (auto picks its own). Measure with: python -m scripts.bench_latency
PROVIDER_SORT = os.environ.get("PROVIDER_SORT", "").strip()
# Optional price cap (USD per million tokens, prompt and completion) for the CHEAP tier's provider, so a speed
# preference (:nitro / sort) can't silently route to a pricier provider. e.g. CHEAP_MAX_PRICE=0.05
CHEAP_MAX_PRICE = float(os.environ.get("CHEAP_MAX_PRICE", "0") or 0)

DATA_DB = os.environ.get("DATA_DB", "sample_supplies")
DATA_COLLECTION = os.environ.get("DATA_COLLECTION", "sales")
APP_DB = os.environ.get("APP_DB", "downshift")

# Share of a skill's test questions the cheap model must get right for the skill to go live
GATE_PASS_RATE = float(os.environ.get("GATE_PASS_RATE", "0.85"))
# On gate rejection, reflect on failing vs passing traces and re-gate once (0 disables)
REFLECT_ON_REJECT = int(os.environ.get("REFLECT_ON_REJECT", "1"))

# Query safety limits
MAX_TIME_MS = 15_000
MAX_RESULT_ROWS = 200
