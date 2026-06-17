"""Tracing across the route lifecycle.

A minimal in-process tracer: spans with durations that roll up to a route total.
Each span carries a real epoch timestamp so traces can be correlated and exported
as JSON lines.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    epoch_ms: float  
    start_ms: float
    duration_ms: float = 0.0


@dataclass
class Trace:
    spans: list[Span] = field(default_factory=list)

    @contextmanager
    def span(self, name: str):
        start = time.perf_counter()
        s = Span(name=name, epoch_ms=time.time() * 1000, start_ms=start * 1000)
        try:
            yield s
        finally:
            s.duration_ms = (time.perf_counter() - start) * 1000
            self.spans.append(s)

    def total_ms(self) -> float:
        return sum(s.duration_ms for s in self.spans)

    def to_jsonl(self) -> str:
        """One JSON object per span."""
        return "\n".join(
            json.dumps(
                {
                    "name": s.name,
                    "epoch_ms": round(s.epoch_ms, 3),
                    "duration_ms": round(s.duration_ms, 3),
                }
            )
            for s in self.spans
        )
