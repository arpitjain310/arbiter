"""SQLite backend

Runs SQL against a SQLite database for the queries it understands
(COUNT over a known table), and reports anything else as an error Result so the
router's fallback path handles it like any other backend miss. Proves the
contract holds against real storage and gives the eval harness one real latency
measurement.
"""
from __future__ import annotations

import sqlite3
import threading
import time

from ..backend import Backend, Query, Result

_KEYWORDS = ["count", "rows", "table", "sum", "average"]
_TABLES = ("orders", "customers")


class SQLiteBackend(Backend):
    name = "sql"

    def __init__(
        self,
        db_path: str = ":memory:",
        cost_usd: float = 0.0,
        expected_latency_ms: float = 8.0,
    ) -> None:
        self.cost_usd = cost_usd
        self.expected_latency_ms = expected_latency_ms
        # check_same_thread=False i.e. the router queries backends from a thread pool.
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._seed()

    def _seed(self) -> None:
        """Create and populate the schema once; safe to call on an existing db."""
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, total REAL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT)"
            )
            if self._conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
                self._conn.executemany(
                    "INSERT INTO orders (total) VALUES (?)", [(19.99,), (5.0,), (250.0,)]
                )
            if self._conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
                self._conn.executemany(
                    "INSERT INTO customers (name) VALUES (?)", [("ada",), ("alan",)]
                )

    def can_handle(self, query: Query) -> float:
        text = query.text.lower()
        hits = sum(1 for k in _KEYWORDS if k in text)
        return min(1.0, hits / len(_KEYWORDS))

    def query(self, query: Query) -> Result:
        text = query.text.lower()
        start = time.perf_counter()
        table = next((t for t in _TABLES if t in text), None)
        if "count" not in text or table is None:
            return Result(
                backend=self.name,
                content="",
                error="unsupported query (only COUNT over a known table)",
            )
        try:
            with self._lock:
                # table is from a fixed whitelist, not user input.
                n = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.Error as exc:
            return Result(backend=self.name, content="", error=str(exc))
        latency_ms = (time.perf_counter() - start) * 1000
        return Result(
            backend=self.name,
            content=f"{table} has {n} rows",
            latency_ms=latency_ms,
            cost_usd=self.cost_usd,
        )

    def close(self) -> None:
        self._conn.close()
