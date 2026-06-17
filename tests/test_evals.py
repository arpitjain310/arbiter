from router.backends.mock import default_backends
from router.classify import select_all
from router.evals.harness import DATASETS_DIR, load_cases, run_evals
from router.router import Router


def _report():
    cases = load_cases(DATASETS_DIR / "example.jsonl")
    return run_evals(Router(default_backends(), retry_backoff_s=0), cases)


def test_eval_harness_runs():
    report = _report()
    assert report.n == len(load_cases(DATASETS_DIR / "example.jsonl"))
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert 0.0 <= report.answer_accuracy <= 1.0
    assert 0.0 <= report.degradation_rate <= 1.0


def test_routing_meets_precision_recall_gate():
    # Regression gate: routing quality must clear these or CI fails..
    report = _report()
    assert report.precision >= 0.70, f"precision regressed: {report.precision:.0%}"
    assert report.recall >= 0.70, f"recall regressed: {report.recall:.0%}"


def test_threshold_classifier_beats_route_all_on_precision():
    # The argument the eval makes: routing to everything maxes recall but tanks
    # precision.
    cases = load_cases(DATASETS_DIR / "example.jsonl")
    threshold = run_evals(Router(default_backends(), retry_backoff_s=0), cases)
    baseline = run_evals(
        Router(default_backends(), retry_backoff_s=0, classifier=select_all), cases
    )
    assert threshold.precision > baseline.precision
    assert baseline.recall >= threshold.recall
