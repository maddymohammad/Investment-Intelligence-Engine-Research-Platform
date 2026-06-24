"""Integration tests for database layer — uses a real in-memory SQLite DB."""
import os
import pytest
from datetime import date, datetime

os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder")


@pytest.fixture(autouse=True)
def _init_db():
    """Ensure tables exist before each test."""
    from src.storage.db import init_db
    init_db()


@pytest.fixture
def session():
    """Fresh session per test — prevents cascading failures between tests."""
    from src.storage.db import get_session
    with get_session() as s:
        yield s


def _stock_data(symbol="TCS.NS", cap="LARGE", active=True, **extra):
    d = {
        "symbol": symbol,
        "name": f"Test Corp {symbol}",
        "exchange": "NSE",
        "sector": "Technology",
        "cap_category": cap,
        "is_active": active,
    }
    d.update(extra)
    return d


class TestStockRepository:
    def test_upsert_and_retrieve(self, session):
        from src.storage.repository import StockRepository
        repo = StockRepository()

        repo.upsert(session, _stock_data("TCS.NS", "LARGE"))
        session.flush()

        stock = repo.get_by_symbol(session, "TCS.NS")
        assert stock is not None
        assert stock.symbol == "TCS.NS"
        assert stock.cap_category == "LARGE"
        assert stock.exchange == "NSE"

    def test_update_existing(self, session):
        from src.storage.repository import StockRepository
        repo = StockRepository()

        repo.upsert(session, _stock_data("TCS.NS"))
        session.flush()
        repo.upsert(session, _stock_data("TCS.NS", name="TCS Updated"))
        session.flush()

        stock = repo.get_by_symbol(session, "TCS.NS")
        assert stock.name == "TCS Updated"

    def test_get_active_filters_inactive(self, session):
        from src.storage.repository import StockRepository
        repo = StockRepository()

        repo.upsert(session, _stock_data("ACTIVE.NS", active=True))
        repo.upsert(session, _stock_data("INACTIVE.NS", active=False))
        session.flush()

        active = repo.get_active(session)
        symbols = [s.symbol for s in active]
        assert "ACTIVE.NS" in symbols
        assert "INACTIVE.NS" not in symbols

    def test_count_only_active(self, session):
        from src.storage.repository import StockRepository
        repo = StockRepository()

        repo.upsert(session, _stock_data("A.NS", active=True))
        repo.upsert(session, _stock_data("B.NS", active=False))
        session.flush()

        count = repo.count(session)
        assert count >= 1  # at least A.NS


class TestRunLogRepository:
    def test_create_and_get_latest(self, session):
        from src.storage.repository import RunLogRepository

        repo = RunLogRepository()
        run_date = date(2024, 1, 15)
        log = repo.create(session, run_date, datetime.utcnow())
        session.flush()

        assert log.id is not None
        assert log.run_date == run_date

        latest = repo.get_latest(session)
        assert latest is not None

    def test_update_status(self, session):
        from src.storage.repository import RunLogRepository

        repo = RunLogRepository()
        log = repo.create(session, date(2024, 1, 16), datetime.utcnow())
        session.flush()

        repo.update(session, log.id, status="SUCCESS", stocks_selected=3)
        session.flush()

        updated = session.get(log.__class__, log.id)
        assert updated.status == "SUCCESS"
        assert updated.stocks_selected == 3

    def test_update_report_path(self, session):
        from src.storage.repository import RunLogRepository

        repo = RunLogRepository()
        log = repo.create(session, date(2024, 2, 1), datetime.utcnow())
        session.flush()

        repo.update(session, log.id, report_path="reports/daily/2024-02-01.md")
        session.flush()

        updated = session.get(log.__class__, log.id)
        assert updated.report_path == "reports/daily/2024-02-01.md"


class TestReportRepository:
    def test_upsert_and_retrieve(self, session):
        from src.storage.repository import ReportRepository

        repo = ReportRepository()
        run_date = date(2024, 1, 17)

        repo.upsert(session, {
            "run_date": run_date,
            "markdown_path": "reports/daily/2024-01-17.md",
        })
        session.flush()

        report = repo.get_by_date(session, run_date)
        assert report is not None
        assert report.markdown_path == "reports/daily/2024-01-17.md"

    def test_upsert_updates_existing(self, session):
        from src.storage.repository import ReportRepository

        repo = ReportRepository()
        run_date = date(2024, 1, 18)

        repo.upsert(session, {"run_date": run_date, "markdown_path": "reports/v1.md"})
        session.flush()
        repo.upsert(session, {"run_date": run_date, "markdown_path": "reports/v2.md"})
        session.flush()

        report = repo.get_by_date(session, run_date)
        assert report.markdown_path == "reports/v2.md"
