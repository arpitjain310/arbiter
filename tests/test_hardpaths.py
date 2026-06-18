from router.backend import Query
from router.backends.mock import default_backends
from router.budget import Budget
from router.classify import select_backends
from router.router import FallbackRung, Router


def test_timeout_triggers_the_fallback_ladder():
    backends = default_backends()
    by_name = {b.name: b for b in backends}
    by_name["sql"].set_delay(0.2)

    budget = Budget(max_latency_ms=20)
    resp = Router(backends, budget=budget, retry_backoff_s=0).route(Query("count the rows"))
    # The only routed backend timed out on primary + retry, so the ladder ran on
    # and a dropped backend answered instead of the route raising.
    assert not resp.degraded
    assert FallbackRung.SECONDARY in resp.decision.fallback_rungs


def test_budget_drops_a_branch_that_exceeds_the_latency_ceiling():
    backends = default_backends()
    kept = Budget(max_latency_ms=50).affordable(backends, Query("x"))
    names = [b.name for b in kept]
    assert "web" not in names and "api" not in names
    assert all(b.expected_latency_ms <= 50 for b in kept)


def test_classifier_handles_empty_backend_list():
    assert select_backends(Query("anything"), []) == []


def test_router_degrades_cleanly_with_no_backends():
    resp = Router([], retry_backoff_s=0).route(Query("anything"))
    assert resp.degraded
    assert "[degraded]" in resp.merged
