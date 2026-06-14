from router.backends.mock import default_backends
from router.evals.harness import DATASETS_DIR, load_cases, run_evals
from router.router import Router


def test_eval_harness_runs():
    cases = load_cases(DATASETS_DIR / "example.jsonl")
    report = run_evals(Router(default_backends()), cases)
    assert report.n == len(cases)
    assert 0.0 <= report.routing_accuracy <= 1.0
    assert 0.0 <= report.degradation_rate <= 1.0
