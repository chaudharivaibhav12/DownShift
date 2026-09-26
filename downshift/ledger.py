"""One entry per model call or run in the time-series `ledger`, plus a live `events` feed for the console."""
from datetime import datetime, timezone


def log_run(adb, *, mode, path, family, model, cost, tokens_in=0, tokens_out=0, latency_ms=0,
            passed=None, case_id=None, batch_id=None, skill=None, extra=None):
    adb.ledger.insert_one({
        "ts": datetime.now(timezone.utc),
        "meta": {"mode": mode, "family": family, "model": model},
        "path": path,            # baseline | cheap | mid | learn | gate | repair
        "costUsd": cost, "tokensIn": tokens_in, "tokensOut": tokens_out, "latencyMs": latency_ms,
        "passed": passed, "caseId": case_id, "batchId": batch_id,
        "skill": skill, **(extra or {}),
    })


def event(adb, type_, **payload):
    adb.events.insert_one({"ts": datetime.now(timezone.utc), "type": type_, "payload": payload})
