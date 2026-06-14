from router.backend import Query
from router.backends.mock import default_backends
from router.router import Router


def test_degrades_when_all_backends_fail():
    backends = default_backends()
    for b in backends:
        b.set_failing(True)
    resp = Router(backends).route(Query("count rows similar latest weather"))
    assert resp.degraded
    assert "[degraded]" in resp.merged


def test_survives_partial_failure():
    backends = default_backends()
    by_name = {b.name: b for b in backends}
    by_name["sql"].set_failing(True)  # primary fails; another still answers
    resp = Router(backends).route(Query("count rows and explain the concept"))
    assert not resp.degraded
    assert any(r.ok for r in resp.results)
