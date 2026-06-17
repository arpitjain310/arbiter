from __future__ import annotations

import argparse

from .backend import Backend, Query
from .backends.mock import default_backends
from .router import Router


def build_backends(provider: str, db: str) -> list[Backend]:
    """Default mock set, with the SQL backend swapped for real SQLite on demand."""
    backends = default_backends()
    if provider == "sqlite":
        from .backends.sqlite import SQLiteBackend

        backends = [SQLiteBackend(db) if b.name == "sql" else b for b in backends]
    return backends


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="route")
    parser.add_argument("query")
    parser.add_argument("--provider", choices=["mock", "sqlite"], default="mock")
    parser.add_argument("--db", default=":memory:", help="SQLite path for --provider sqlite")
    args = parser.parse_args(argv)

    resp = Router(build_backends(args.provider, args.db)).route(Query(args.query))
    print(resp.merged)
    print(f"\n[trace] {resp.trace.total_ms():.1f}ms over {len(resp.trace.spans)} spans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
