"""Classify a query and select backend(s).

A confidence threshold over Backend.can_handle. Keeping it
behind one function lets an LLM classifier slot in later without the router
caring whether routing is heuristic or learned.
"""
from __future__ import annotations

from .backend import Backend, Query


def select_backends(
    query: Query,
    backends: list[Backend],
    threshold: float = 0.1,
    max_fanout: int = 3,
) -> list[Backend]:
    if not backends:
        return []
    scored = [(b.can_handle(query), b) for b in backends]
    chosen = [
        b for score, b in sorted(scored, key=lambda s: s[0], reverse=True)
        if score >= threshold
    ]
    if not chosen:
        # Never return empty: degrade to the cheapest backend.
        chosen = [min(backends, key=lambda b: b.cost_usd)]
    return chosen[:max_fanout]


def select_all(query: Query, backends: list[Backend]) -> list[Backend]:
    """Route to every backend. Maximal recall, poor precision — the baseline the
    eval harness measures the threshold classifier against."""
    return list(backends)
