"""Eval harness

The harness runs the
router over a dataset and reports metrics: routing accuracy, degradation rate,
latency/cost. 
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
    routing_accuracy: float
    degradation_rate: float
    avg_latency_ms: float
    avg_cost_usd: float

    def __str__(self) -> str:
        return (
            f"cases={self.n}  routing_acc={self.routing_accuracy:.0%}  "
            f"degraded={self.degradation_rate:.0%}  "
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
    routed_right = 0
    degraded = 0
    latency = 0.0
    cost = 0.0
    for case in cases:
        resp = router.route(Query(case.query))
        hit_backends = {r.backend for r in resp.results if r.ok}
        if set(case.expected_backends) <= hit_backends:
            routed_right += 1
        if resp.degraded:
            degraded += 1
        latency += resp.trace.total_ms()
        cost += sum(r.cost_usd for r in resp.results)
    n = max(1, len(cases))

    return EvalReport(
        n=len(cases),
        routing_accuracy=routed_right / n,
        degradation_rate=degraded / n,
        avg_latency_ms=latency / n,
        avg_cost_usd=cost / n,
    )


def main() -> int:
    from ..backends.mock import default_backends

    cases = load_cases(DATASETS_DIR / "example.jsonl")
    report = run_evals(Router(default_backends()), cases)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
