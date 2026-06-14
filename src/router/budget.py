"""Per-route latency + cost budget.

The router consults the budget before fan-out to drop backends it can't afford.
"""
from __future__ import annotations

from dataclasses import dataclass

from .backend import Backend, Query


@dataclass
class Budget:
    max_latency_ms: float = 500.0
    max_cost_usd: float = 0.05

    def affordable(self, backends: list[Backend], query: Query) -> list[Backend]:
        """Drop backends whose advertised cost increases the budget too much.
        """
        out: list[Backend] = []
        spent = 0.0
        for b in backends:
            cost = getattr(b, "cost_usd", 0.0)
            if spent + cost <= self.max_cost_usd:
                out.append(b)
                spent += cost
        return out
