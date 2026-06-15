"""Per-route latency + cost budget.

The router consults the budget before fan-out to drop backends it can't afford.
With parallel fan-out, route latency equals the slowest backend (not the sum);
cost still accumulates since all chosen backends run concurrently.
"""
from __future__ import annotations

from dataclasses import dataclass

from .backend import Backend, Query


@dataclass
class Budget:
    max_latency_ms: float = 500.0
    max_cost_usd: float = 0.05

    def affordable(self, backends: list[Backend], query: Query) -> list[Backend]:
        """Keep backends that fit within the cost and latency ceilings.

        Latency is modelled as the slowest branch (parallel fan-out); cost
        accumulates across all chosen backends.
        """
        out: list[Backend] = []
        spent = 0.0
        max_latency = 0.0
        for b in backends:
            new_cost = spent + b.cost_usd
            new_latency = max(max_latency, b.expected_latency_ms)
            if new_cost <= self.max_cost_usd and new_latency <= self.max_latency_ms:
                out.append(b)
                spent = new_cost
                max_latency = new_latency
        return out
