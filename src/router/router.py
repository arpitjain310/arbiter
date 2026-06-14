"""The router: classify -> budget -> fan out -> merge -> degrade .

Fan-out, merge, and especially fallback are the systems concerns here. Tests
target the routing and fallback paths specifically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .backend import Backend, Query, Result
from .budget import Budget
from .classify import select_backends
from .observability import Trace


@dataclass
class RouterResponse:
    query: str
    results: list[Result]
    merged: str
    trace: Trace = field(default_factory=Trace)

    @property
    def degraded(self) -> bool:
        """True when no backend produced a usable answer."""
        return not any(r.ok for r in self.results)


class Router:
    def __init__(self, backends: list[Backend], budget: Budget | None = None) -> None:
        self.backends = backends
        self.budget = budget or Budget()

    def route(self, query: Query) -> RouterResponse:
        trace = Trace()
        with trace.span("classify"):
            chosen = select_backends(query, self.backends)
        with trace.span("budget"):
            chosen = self.budget.affordable(chosen, query)

        results: list[Result] = []

        for backend in chosen:
            with trace.span(f"query:{backend.name}"):
                results.append(backend.query(query))

        with trace.span("merge"):
            merged = self._merge(query, results)
        return RouterResponse(query.text, results, merged, trace)

    def _merge(self, query: Query, results: list[Result]) -> str:
        ok = [r for r in results if r.ok]
        if not ok:
            return self._fallback(query, results)
        return "\n".join(r.content for r in ok)

    def _fallback(self, query: Query, results: list[Result]) -> str:
        """Graceful degradation: every chosen backend failed.
        """
        errors = "; ".join(r.error or "" for r in results) or "no backend selected"
        return f"[degraded] no backend answered ({errors})"
