"""Turn an experiment summary into a flat table of named, citable numbers ("facts")."""
from typing import Any


def flatten_facts(summary: dict[str, Any]) -> dict[str, float]:
    facts: dict[str, float] = {}
    for label, e in summary.get("algos", {}).items():
        facts[f"{label}.n"] = float(e["n"])
        facts[f"{label}.fill_rate"] = float(e["fill_rate"])
        for metric, v in e.items():
            if isinstance(v, dict):
                for k in ("mean", "ci_low", "ci_high"):
                    facts[f"{label}.{metric}.{k}"] = float(v[k])
    for label, per_metric in summary.get("paired_vs_baseline", {}).items():
        for metric, v in per_metric.items():
            for k in ("mean_diff", "ci_low", "ci_high", "sign_test_p"):
                facts[f"{label}.paired.{metric}.{k}"] = float(v[k])
    return facts
