"""Sensitivity sweeps (E2 venue settings, E5 robustness): run the same experiment under variants.

A variant is a dict of ExperimentConfig field overrides, e.g. {"venue": {"latency_ms": 30000}} or
{"qty": 120}. Every variant uses the same seed, hence the same parent orders. Compare variants to the
"default" one to see how much a setting moves the measured cost.
"""
from dataclasses import replace

from execscope.experiments.harness import ExperimentConfig, run_experiment


def run_variants(base: ExperimentConfig, variants: dict[str, dict]) -> dict[str, dict]:
    """label -> summary.json-style dict. A 'default' variant (no overrides) is always included first."""
    out = {}
    for label, over in {"default": {}, **variants}.items():
        cfg = replace(base, name=f"{base.name}__{label}", **over)
        _, summary, _ = run_experiment(cfg)
        out[label] = summary
    return out


def cost_shift_table(results: dict[str, dict], algo: str, metric: str = "vs_arrival_bps") -> list[dict]:
    """Mean `metric` of `algo` per variant and its shift versus 'default'."""
    base = results["default"]["algos"][algo][metric]["mean"]
    return [
        {"variant": label, "mean": r["algos"][algo][metric]["mean"], "shift_vs_default": r["algos"][algo][metric]["mean"] - base,
         "ci_low": r["algos"][algo][metric]["ci_low"], "ci_high": r["algos"][algo][metric]["ci_high"]}
        for label, r in results.items()
    ]
