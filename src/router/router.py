"""The router: classify -> budget -> fan out -> merge -> degrade .

Fan-out is parallel: each backend runs in its own thread with a per-backend
timeout derived from the latency budget. A timed-out or failed backend becomes
Result(error=...) so merge and fallback handle it.
"""
from __future__ import annotations

import concurrent.futures
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
        timeout_s = self.budget.max_latency_ms / 1000

        with trace.span("fanout"):
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, len(chosen))
            ) as ex:
                future_to_backend = {ex.submit(b.query, query): b for b in chosen}
                done, pending = concurrent.futures.wait(
                    future_to_backend, timeout=timeout_s
                )
            for fut in done:
                backend = future_to_backend[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:
                    results.append(Result(backend=backend.name, content="", error=str(exc)))
            for fut in pending:
                fut.cancel()
                backend = future_to_backend[fut]
                results.append(Result(backend=backend.name, content="", error="timeout"))

        with trace.span("merge"):
            merged = self._merge(query, results)
        return RouterResponse(query.text, results, merged, trace)

    def _merge(self, query: Query, results: list[Result]) -> str:
        ok = [r for r in results if r.ok]
        if not ok:
            return self._fallback(query, results)
        return "\n".join(r.content for r in ok)

    def _fallback(self, query: Query, results: list[Result]) -> str:
        """Graceful degradation: every chosen backend failed or timed out.
        """
        errors = "; ".join(r.error or "" for r in results) or "no backend selected"
        return f"[degraded] no backend answered ({errors})"
