"""Report writers. `template_writer` is deterministic; an LLM writer can be plugged in via the same
signature and is accepted only if `verify.ungrounded_numbers` finds nothing."""
from collections.abc import Callable
from dataclasses import dataclass

from execscope.explain.facts import flatten_facts
from execscope.explain.verify import ungrounded_numbers

Writer = Callable[[dict, dict], str]   # (summary, facts) -> markdown text


def template_writer(summary: dict, facts: dict) -> str:
    lines = ["## Execution cost summary", ""]
    for label, e in summary["algos"].items():
        v = e.get("vs_vwap_bps")
        if not v:
            continue
        lines.append(f"- **{label}**: {v['mean']:.2f} bp versus interval VWAP "
                     f"(95% interval {v['ci_low']:.2f} to {v['ci_high']:.2f}), "
                     f"{e['n']} parent orders, fill rate {e['fill_rate']:.2f}.")
    for label, per in summary.get("paired_vs_baseline", {}).items():
        d = per.get("vs_vwap_bps")
        if not d:
            continue
        verdict = ("the interval excludes zero" if d["ci_low"] > 0 or d["ci_high"] < 0
                   else "the interval includes zero, so there is no clear difference")
        lines.append(f"- **{label} minus baseline**: mean difference {d['mean_diff']:.2f} bp "
                     f"({d['ci_low']:.2f} to {d['ci_high']:.2f}); {verdict}; sign-test p = {d['sign_test_p']:.3f}.")
    lines += ["", "Negative cost means cheaper than the benchmark. Differences whose interval includes zero "
              "should not be read as evidence of a better algorithm."]
    return "\n".join(lines)


@dataclass(frozen=True)
class Explanation:
    text: str
    verified: bool
    rejected_numbers: list[str]     # numbers the first writer used that no fact supports
    used_fallback: bool


def explain(summary: dict, writer: Writer = template_writer) -> Explanation:
    facts = flatten_facts(summary)
    draft = writer(summary, facts)
    bad = ungrounded_numbers(draft, facts)
    if not bad:
        return Explanation(draft, True, [], False)
    fallback = template_writer(summary, facts)
    return Explanation(fallback, not ungrounded_numbers(fallback, facts), bad, True)
