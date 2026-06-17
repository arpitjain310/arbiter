"""Eval harness: measure routing quality over a labeled dataset.

A case is (query, expected_backends, expect_contains). Routing quality is
precision and recall over the backends the router *chose* (the decision record),
not over which backends happened to answer — so a correct route to a down
backend still scores as good routing. Answer quality is a substring check
against the merged reply.

Run over the bundled dataset:  python -m router.evals.harness
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..backend import Query
from ..router import Router

DATASETS_DIR = Path(__file__).parent / "datasets"


@dataclass
class Case:
    query: str
    expected_backends: list[str]
    expect_contains: list[str]


@dataclass
class EvalReport:
    n: int
    precision: float       # of the backends routed to, how many were needed
    recall: float          # of the backends needed, how many were routed to
    answer_accuracy: float  # merged reply contained the expected substrings
    degradation_rate: float
    avg_latency_ms: float  # reported per-call latency, slowest branch (parallel)
    avg_cost_usd: float

    def __str__(self) -> str:
        return (
            f"cases={self.n}  precision={self.precision:.0%}  recall={self.recall:.0%}  "
            f"answer_acc={self.answer_accuracy:.0%}  degraded={self.degradation_rate:.0%}  "
            f"latency={self.avg_latency_ms:.1f}ms  cost=${self.avg_cost_usd:.4f}"
        )


def load_cases(path: Path) -> list[Case]:
    cases: list[Case] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        cases.append(
            Case(d["query"], d.get("expected_backends", []), d.get("expect_contains", []))
        )
    return cases


def run_evals(router: Router, cases: list[Case]) -> EvalReport:
    precision_sum = 0.0
    recall_sum = 0.0
    answer_hits = 0
    answer_total = 0
    degraded = 0
    latency = 0.0
    cost = 0.0
    for case in cases:
        resp = router.route(Query(case.query))
        # Routed-to comes from the decision, not the results: a correct route to
        # a failing backend is still a correct route.
        routed = set(resp.decision.chosen)
        expected = set(case.expected_backends)
        correct = routed & expected
        if routed:
            precision_sum += len(correct) / len(routed)
        if expected:
            recall_sum += len(correct) / len(expected)

        if case.expect_contains:
            answer_total += 1
            merged = resp.merged.lower()
            if all(s.lower() in merged for s in case.expect_contains):
                answer_hits += 1

        if resp.degraded:
            degraded += 1
        ok_latencies = [r.latency_ms for r in resp.results if r.ok]
        latency += max(ok_latencies) if ok_latencies else 0.0
        cost += sum(r.cost_usd for r in resp.results)

    n = max(1, len(cases))
    return EvalReport(
        n=len(cases),
        precision=precision_sum / n,
        recall=recall_sum / n,
        answer_accuracy=answer_hits / max(1, answer_total),
        degradation_rate=degraded / n,
        avg_latency_ms=latency / n,
        avg_cost_usd=cost / n,
    )


def main() -> int:
    from ..backends.mock import default_backends
    from ..classify import select_all

    cases = load_cases(DATASETS_DIR / "example.jsonl")
    threshold = run_evals(Router(default_backends()), cases)
    baseline = run_evals(Router(default_backends(), classifier=select_all), cases)
    # The baseline routes to everything: perfect recall, poor precision. Printing
    # both is the argument — the headline precision means something next to it.
    print(f"threshold classifier   {threshold}")
    print(f"route-all baseline     {baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
