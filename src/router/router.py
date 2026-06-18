"""The router: classify -> budget -> fan out -> merge -> degrade gracefully.

Fan-out is parallel: each backend runs in its own thread with a per-backend
timeout from the latency budget. When the primary fan-out yields nothing usable,
a designed fallback ladder runs (retry -> secondary -> degraded) instead of a
exception. Every routing decision is recorded so "why this route" is
always answerable.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from enum import Enum

from .backend import Backend, Query, Result
from .budget import Budget
from .classify import select_backends
from .observability import Trace

Classifier = Callable[[Query, list[Backend]], list[Backend]]


class FallbackRung(Enum):
    """Steps of the fallback ladder, in the order they are tried."""

    PRIMARY = "primary"      # the initial parallel fan-out
    RETRY = "retry"          # retried the primary backends once after a backoff
    SECONDARY = "secondary"  # routed to a backend the classifier or budget dropped
    DEGRADED = "degraded"    # nothing answered; returned a disclosed degraded reply


@dataclass
class RoutingDecision:
    """What the router chose, what it dropped, and how far down the ladder it went."""

    chosen: list[str] = field(default_factory=list)
    dropped_by_classifier: list[str] = field(default_factory=list)
    dropped_by_budget: list[str] = field(default_factory=list)
    fallback_rungs: list[FallbackRung] = field(default_factory=list)


@dataclass
class RouterResponse:
    query: str
    results: list[Result]
    merged: str
    trace: Trace = field(default_factory=Trace)
    decision: RoutingDecision = field(default_factory=RoutingDecision)

    @property
    def degraded(self) -> bool:
        """True when no backend produced a usable answer."""
        return not any(r.ok for r in self.results)


class Router:
    def __init__(
        self,
        backends: list[Backend],
        budget: Budget | None = None,
        retry_backoff_s: float = 0.05,
        classifier: Classifier | None = None,
    ) -> None:
        self.backends = backends
        self.budget = budget or Budget()
        self.retry_backoff_s = retry_backoff_s
        # Swappable so the eval harness can measure alternative strategies
        self.classifier = classifier or select_backends

    def route(self, query: Query) -> RouterResponse:
        trace = Trace()
        with trace.span("classify"):
            chosen = self.classifier(query, self.backends)
        dropped_by_classifier = [b for b in self.backends if b not in chosen]
        with trace.span("budget"):
            affordable = self.budget.affordable(chosen, query)
        dropped_by_budget = [b for b in chosen if b not in affordable]

        decision = RoutingDecision(
            chosen=[b.name for b in affordable],
            dropped_by_classifier=[b.name for b in dropped_by_classifier],
            dropped_by_budget=[b.name for b in dropped_by_budget],
            fallback_rungs=[FallbackRung.PRIMARY],
        )

        with trace.span("fanout"):
            results = self._fanout(affordable, query)

        if not any(r.ok for r in results):
            # Best candidates chosen first.
            secondaries = dropped_by_budget + dropped_by_classifier
            results = self._fallback_ladder(
                query, affordable, secondaries, results, decision, trace
            )

        with trace.span("merge"):
            merged = self._merge(results)
        return RouterResponse(query.text, results, merged, trace, decision)

    def _fanout(self, backends: list[Backend], query: Query) -> list[Result]:
        """Query backends in parallel; a slow or raising backend becomes an error."""
        results: list[Result] = []
        timeout_s = self.budget.max_latency_ms / 1000
        ex = ThreadPoolExecutor(max_workers=max(1, len(backends)))
        try:
            future_to_backend = {ex.submit(b.query, query): b for b in backends}
            done, pending = wait(future_to_backend, timeout=timeout_s)
            for fut in done:
                backend = future_to_backend[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:
                    results.append(Result(backend=backend.name, content="", error=str(exc)))
            for fut in pending:
                results.append(
                    Result(backend=future_to_backend[fut].name, content="", error="timeout")
                )
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        return results

    def _fallback_ladder(
        self,
        query: Query,
        primary: list[Backend],
        secondaries: list[Backend],
        primary_results: list[Result],
        decision: RoutingDecision,
        trace: Trace,
    ) -> list[Result]:
        """Step down the ladder until something answers, recording each rung.

        Returns the results that produced an answer, or the original failed
        results if the ladder is exhausted (merge then discloses the degradation).
        """
        # Rung 1: retry the primary backends once — a transient outage may clear.
        decision.fallback_rungs.append(FallbackRung.RETRY)
        with trace.span("fallback:retry"):
            time.sleep(self.retry_backoff_s)
            retry_results = self._fanout(primary, query)
        if any(r.ok for r in retry_results):
            return retry_results

        # Rung 2: route to a dropped backend, accepting its cost/latency to get
        # an answer at all. Try them in priority order, stop at the first success.
        for backend in secondaries:
            decision.fallback_rungs.append(FallbackRung.SECONDARY)
            with trace.span(f"fallback:secondary:{backend.name}"):
                secondary_results = self._fanout([backend], query)
            if any(r.ok for r in secondary_results):
                return secondary_results

        # Rung 3: nothing answered. Keep the original failures so merge discloses.
        decision.fallback_rungs.append(FallbackRung.DEGRADED)
        return primary_results

    def _merge(self, results: list[Result]) -> str:
        ok = [r for r in results if r.ok]
        if not ok:
            return self._disclose(results)
        return "\n".join(r.content for r in ok)

    def _disclose(self, results: list[Result]) -> str:
        """Degraded answer with disclosure: every rung of the ladder failed."""
        errors = "; ".join(r.error or "" for r in results) or "no backend selected"
        return f"[degraded] no backend answered ({errors})"
