"""Backend abstraction: a source the router can query.

Each backend declares its latency and cost so the budget can filter
before fan-out. query() surfaces failures as Result(error=...) rather than
raising, so the router degrades gracefully instead of crashing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Query:
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Result:
    backend: str
    content: str
    # Per-call latency and cost; populated by query().
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Backend(ABC):
    name: str
    # Before fan-out so the budget can filter without calling query().
    cost_usd: float
    expected_latency_ms: float

    @abstractmethod
    def can_handle(self, query: Query) -> float:
        """Confidence in [0, 1] that this backend is relevant to the query."""

    @abstractmethod
    def query(self, query: Query) -> Result:
        """Execute the query. Surface failures as Result(error=...) rather than
        raising, so the router can degrade gracefully."""
