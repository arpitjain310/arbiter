import json

from router.backend import Query
from router.backends.mock import default_backends
from router.router import Router


def test_trace_exports_jsonl_with_epoch_timestamps():
    resp = Router(default_backends()).route(Query("count the rows"))
    lines = resp.trace.to_jsonl().splitlines()
    assert len(lines) == len(resp.trace.spans)
    first = json.loads(lines[0])
    assert first["name"]
    assert first["epoch_ms"] > 0
    assert first["duration_ms"] >= 0
