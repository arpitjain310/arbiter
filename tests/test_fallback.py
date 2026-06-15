"""Hard-path tests"""
from router.backend import Query
from router.backends.mock import default_backends
from router.router import FallbackRung, Router


def test_degrades_when_all_backends_fail():
    backends = default_backends()
    for b in backends:
        b.set_failing(True)
    resp = Router(backends, retry_backoff_s=0).route(
        Query("count rows similar latest weather")
    )
    assert resp.degraded
    assert "[degraded]" in resp.merged
    # Ladder ran to exhaustion and disclosed it.
    assert resp.decision.fallback_rungs[-1] is FallbackRung.DEGRADED


def test_survives_partial_failure():
    backends = default_backends()
    by_name = {b.name: b for b in backends}
    by_name["sql"].set_failing(True)  # primary fails; another still answers
    resp = Router(backends).route(Query("count rows and explain the concept"))
    assert not resp.degraded
    assert any(r.ok for r in resp.results)


def test_retry_rung_rides_out_transient_failure():
    backends = default_backends()
    by_name = {b.name: b for b in backends}
    by_name["sql"].fail_n_times(1)  # fails once, recovers on retry
    resp = Router(backends, retry_backoff_s=0).route(Query("count the rows"))
    assert not resp.degraded
    assert resp.decision.fallback_rungs == [FallbackRung.PRIMARY, FallbackRung.RETRY]
    assert any(r.backend == "sql" and r.ok for r in resp.results)


def test_secondary_rung_routes_to_a_dropped_backend():
    backends = default_backends()
    by_name = {b.name: b for b in backends}
    by_name["sql"].set_failing(True)  # the only classified backend stays down
    resp = Router(backends, retry_backoff_s=0).route(Query("count the rows"))
    assert not resp.degraded
    assert FallbackRung.SECONDARY in resp.decision.fallback_rungs
    # The answer came from a backend the classifier had dropped.
    answered = next(r.backend for r in resp.results if r.ok)
    assert answered in resp.decision.dropped_by_classifier


def test_decision_records_chosen_and_dropped():
    backends = default_backends()
    resp = Router(backends).route(Query("count the rows"))
    assert resp.decision.chosen == ["sql"]
    assert set(resp.decision.dropped_by_classifier) == {"vector", "web", "api"}
