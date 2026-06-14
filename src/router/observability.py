"""Tracing across the route lifecycle.

A minimal in-process tracer: nested spans with durations that roll up. 
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    start_ms: float
    duration_ms: float = 0.0


@dataclass
class Trace:
    spans: list[Span] = field(default_factory=list)

    @contextmanager
    def span(self, name: str):
        start = time.perf_counter()
        s = Span(name=name, start_ms=start * 1000)
        try:
            yield s
        finally:
            s.duration_ms = (time.perf_counter() - start) * 1000
            self.spans.append(s)

    def total_ms(self) -> float:
        return sum(s.duration_ms for s in self.spans)
