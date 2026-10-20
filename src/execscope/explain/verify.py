"""Numeric-grounding verifier: every number in a generated explanation must match a known fact.

Used to stop an AI writer from inventing results. A number such as "0.45" is accepted when some fact
rounds to it at the same number of decimals (so "0.45" matches 0.4488). Percent signs and thousands
separators are handled; the fact table also supplies small whole numbers (counts, n).
"""
import re
from collections.abc import Iterable

NUMBER = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?")
ALWAYS_OK = {1.0, 2.0, 3.0, 4.0, 5.0, 95.0}   # small structural numbers ("top 3", "95% interval")


def extract_numbers(text: str) -> list[tuple[str, float, int]]:
    """(raw string, value, decimals) for every number in the text."""
    out = []
    for m in NUMBER.finditer(text):
        raw = m.group(0)
        clean = raw.replace(",", "").replace("−", "-")
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        out.append((raw, float(clean), decimals))
    return out


def _matches(value: float, decimals: int, facts: Iterable[float]) -> bool:
    tol = 0.5 * 10 ** (-decimals)
    for f in facts:
        if abs(f - value) <= tol + 1e-12 or abs(abs(f) - abs(value)) <= tol + 1e-12:
            return True
    return False


def ungrounded_numbers(text: str, facts: dict[str, float]) -> list[str]:
    values = list(facts.values())
    bad = []
    for raw, value, decimals in extract_numbers(text):
        if decimals == 0 and abs(value) in ALWAYS_OK:
            continue
        if not _matches(value, decimals, values):
            bad.append(raw)
    return bad
