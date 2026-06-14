from router.backend import Query
from router.backends.mock import default_backends
from router.classify import select_backends
from router.router import Router


def test_classifies_to_sql():
    chosen = select_backends(Query("count the rows in the table"), default_backends())
    assert chosen[0].name == "sql"


def test_route_merges_results():
    resp = Router(default_backends()).route(Query("explain the concept"))
    assert not resp.degraded
    assert "vector" in resp.merged
    assert resp.trace.total_ms() >= 0


def test_never_routes_to_empty():
    # A query matching no keywords still resolves to a backend (cheapest).
    chosen = select_backends(Query("zzz qqq"), default_backends())
    assert len(chosen) >= 1
