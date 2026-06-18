"""Mock backends.

Each backend matches on keywords and can be told to fail, so routing and
graceful-degradation paths are deterministic in tests.
"""
from __future__ import annotations

import time

from ..backend import Backend, Query, Result


class MockBackend(Backend):
    def __init__(
        self,
        name: str,
        keywords: list[str],
        latency_ms: float = 5.0,
        cost_usd: float = 0.0,
    ) -> None:
        self.name = name
        self.keywords = keywords
        self.expected_latency_ms = latency_ms
        self.cost_usd = cost_usd
        self._failing = False
        self._fail_remaining = 0
        self._delay = 0.0

    def set_failing(self, failing: bool = True) -> None:
        """Arrange for query() to report an error, simulating an outage."""
        self._failing = failing

    def set_delay(self, seconds: float) -> None:
        """Make query() block, so it can overrun the latency budget and time out."""
        self._delay = seconds

    def fail_n_times(self, n: int) -> None:
        """Fail the next n queries, then recover.The fallback ladder's retry logic should absorb these failures.."""
        self._fail_remaining = n

    def can_handle(self, query: Query) -> float:
        text = query.text.lower()
        hits = sum(1 for k in self.keywords if k in text)
        return min(1.0, hits / max(1, len(self.keywords)))

    def query(self, query: Query) -> Result:
        if self._delay:
            time.sleep(self._delay)
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            return Result(backend=self.name, content="", error="transient failure")
        if self._failing:
            return Result(backend=self.name, content="", error="injected failure")
        return Result(
            backend=self.name,
            content=f"[{self.name}] answer for: {query.text}",
            latency_ms=self.expected_latency_ms,
            cost_usd=self.cost_usd,
        )


def default_backends() -> list[MockBackend]:
    """Four backends: SQL, vector, web, and API."""
    return [
        MockBackend("sql", ["count", "sum", "average", "rows", "table"], latency_ms=8),
        MockBackend("vector", ["similar", "about", "explain", "concept"], latency_ms=20),
        MockBackend("web", ["latest", "news", "today", "current"], latency_ms=120, cost_usd=0.002),
        MockBackend("api", ["weather", "stock", "price"], latency_ms=60, cost_usd=0.001),
    ]
