"""Deterministic date guardrail: find the one calendar period a question names and check the model's dates.

Small models slip on date arithmetic ("November 2013" -> 2013-11-01..2014-01-01). When a question names exactly one
clear period (a month, quarter, half or year) we know the right [start, end) range, so a skill fill that disagrees is
rejected and escalated. Anything ambiguous (ranges like "January through March", two periods, relative dates) is
left alone: the check only speaks when it is sure.
"""
import re
from datetime import datetime, timezone

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
ORD = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "last": 4}
RANGE_WORDS = re.compile(r"\b(through|thru|to|until|till|between|from|since|before|after|vs|versus|compared)\b|\d\s*[-–]\s*\d")
YEAR = r"((?:19|20)\d{2})"


def _d(y, m):
    while m > 12:
        y, m = y + 1, m - 12
    return datetime(y, m, 1, tzinfo=timezone.utc)


def period(question: str):
    """Return (start, end_exclusive) if the question names exactly one clear calendar period, else None."""
    q = question.lower()
    if RANGE_WORDS.search(q):
        return None
    found = set()
    for m in re.finditer(r"\bq([1-4])\s*(?:of\s*)?" + YEAR, q):
        n, y = int(m.group(1)), int(m.group(2)); found.add((_d(y, 3 * n - 2), _d(y, 3 * n + 1)))
    for m in re.finditer(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|last)\s+quarter\s+(?:of\s+)?" + YEAR, q):
        n, y = ORD[m.group(1)], int(m.group(2)); found.add((_d(y, 3 * n - 2), _d(y, 3 * n + 1)))
    for m in re.finditer(r"\b(?:(first|second|1st|2nd|last)\s+half\s+(?:of\s+)?|h([12])\s*)" + YEAR, q):
        n = 1 if (m.group(1) or "") in ("first", "1st") or m.group(2) == "1" else 2
        y = int(m.group(3)); found.add((_d(y, 6 * n - 5), _d(y, 6 * n + 1)))
    month_pat = r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?,?\s+(?:of\s+)?" + YEAR
    for m in re.finditer(month_pat, q):
        y, mo = int(m.group(2)), MONTHS[m.group(1)]; found.add((_d(y, mo), _d(y, mo + 1)))
    if not found:
        years = set(re.findall(r"\b" + YEAR + r"\b", q))
        if len(years) == 1:
            y = int(years.pop()); found.add((_d(y, 1), _d(y + 1, 1)))
    else:  # a finer period was named; any other bare year must be that period's year
        years = {int(y) for y in re.findall(r"\b" + YEAR + r"\b", q)}
        if len(years) > 1:
            return None
    return found.pop() if len(found) == 1 else None


def check_dates(spec: dict, typed: dict, question: str) -> str | None:
    """None if fine; else a message. Only for skills with exactly two date params (a start and an end)."""
    dates = [k for k, s in spec.items() if s.get("type") == "date"]
    if len(dates) != 2 or any(typed.get(k) is None for k in dates):
        return None
    p = period(question)
    if not p:
        return None
    lo, hi = sorted((typed[dates[0]], typed[dates[1]]))
    if (lo, hi) != p:
        return (f"dates {lo:%Y-%m-%d}..{hi:%Y-%m-%d} don't match the period in the question "
                f"({p[0]:%Y-%m-%d}..{p[1]:%Y-%m-%d})")
    return None
