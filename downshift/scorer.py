"""Compare a query result with a test case's expected rows.

Field names are ignored on purpose (a model may call it `revenue`, `totalRevenue` or `total`).
A row matches an expected {label, value} when the label appears among the row's strings and the value
appears among its numbers (within tolerance). Rates may be fractions or percentages.
"""
from bson import Decimal128


def _flatten(v, strings, numbers):
    if isinstance(v, dict):
        for x in v.values():
            _flatten(x, strings, numbers)
    elif isinstance(v, (list, tuple)):
        for x in v:
            _flatten(x, strings, numbers)
    elif isinstance(v, bool) or v is None:
        return
    elif isinstance(v, str):
        strings.append(v.strip().lower())
    elif isinstance(v, Decimal128):
        numbers.append(float(v.to_decimal()))
    elif isinstance(v, (int, float)):
        numbers.append(float(v))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.01, 0.005 * abs(b))


def _row_value(row: dict, expected: dict, rate: bool) -> float | None:
    """If `row` matches `expected`, return the expected value it matched on; else None."""
    strings, numbers = [], []
    _flatten(row, strings, numbers)
    if str(expected["label"]).strip().lower() not in strings:
        return None
    target = expected["value"]
    for n in numbers:
        if _close(n, target) or (rate and abs(n - target * 100) <= 0.5):
            return target
    return None


def score(actual: list[dict] | None, case: dict) -> tuple[bool, str]:
    expected = case["expectedRows"]
    if actual is None:
        return False, "no result"
    if len(actual) != len(expected):
        return False, f"expected {len(expected)} rows, got {len(actual)}"

    matched_values = []
    used = set()
    for row in actual:
        hit = None
        for i, exp in enumerate(expected):
            if i in used:
                continue
            v = _row_value(row, exp, case.get("rate", False))
            if v is not None:
                hit = i
                matched_values.append(v)
                break
        if hit is None:
            return False, f"row not in expected answer: {str(row)[:120]}"
        used.add(hit)

    if case.get("ordered"):
        if any(a < b for a, b in zip(matched_values, matched_values[1:])):
            return False, "rows are in the wrong order"
    return True, "ok"
