"""Backend abstraction: a source the router can query.

The router speaks only this contract. query() reports failure as
Result(error=...) rather than raising, so the router can degrade gracefully
instead of crashing the whole route.
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
    # Observability: per-call latency + cost feed budgeting and tracing.
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Backend(ABC):
    name: str

    @abstractmethod
    def can_handle(self, query: Query) -> float:
        """Confidence in [0, 1] that this backend is relevant to the query.
        The classifier uses this to pick backend(s)."""

    @abstractmethod
    def query(self, query: Query) -> Result:
        """Execute the query. Surface failures as Result(error=...) rather than
        raising, so the router can degrade gracefully."""
