from router.backend import Query
from router.backends.mock import default_backends
from router.backends.sqlite import SQLiteBackend
from router.router import Router


def _with_sqlite(db=":memory:"):
    return [SQLiteBackend(db) if b.name == "sql" else b for b in default_backends()]


def test_sqlite_backend_counts_real_rows():
    resp = Router(_with_sqlite()).route(Query("count the rows in the orders table"))
    assert not resp.degraded
    sql = next(r for r in resp.results if r.backend == "sql")
    assert sql.ok
    assert "orders has 3 rows" in sql.content
    assert sql.latency_ms >= 0


def test_sqlite_reports_unsupported_query_as_error():
    backend = SQLiteBackend()
    res = backend.query(Query("explain the orders table"))  # no COUNT intent
    assert not res.ok
    assert "unsupported" in res.error
    backend.close()


def test_sqlite_setup_is_idempotent(tmp_path):
    db = str(tmp_path / "arbiter.db")
    first = SQLiteBackend(db)
    second = SQLiteBackend(db)  # re-init against a seeded db must not double-seed
    res = second.query(Query("count rows in the orders table"))
    assert "orders has 3 rows" in res.content
    first.close()
    second.close()
