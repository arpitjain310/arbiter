from __future__ import annotations

import argparse

from .backend import Query
from .backends.mock import default_backends
from .router import Router


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="route")
    parser.add_argument("query")
    args = parser.parse_args(argv)

    resp = Router(default_backends()).route(Query(args.query))
    print(resp.merged)
    print(f"\n[trace] {resp.trace.total_ms():.1f}ms over {len(resp.trace.spans)} spans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
