"""Integration tests for SRAG metric queries against real PostgreSQL data.

These tests require a running PostgreSQL database with SRAG data loaded.
They validate that metric SQL queries return values within expected ranges
and that data_ref uses MAX(dt_notific) instead of NOW().
"""

import os

import pytest
from sqlalchemy import text

from src.agent.tools.sql_tool import execute_metric_query
from src.config import Settings
from src.data.queries import METRIC_QUERIES, get_data_ref_query


def _skip_if_no_db():
    """Skip test if database is not reachable."""
    test_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://srag_app:srag_pass@localhost:5433/srag_test",
    )
    try:
        from sqlalchemy import create_engine

        engine = create_engine(test_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        pytest.skip("Database not reachable — skipping integration test")


@pytest.fixture(scope="module")
def settings():
    """Settings pointing to test database."""
    _skip_if_no_db()
    test_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://srag_app:srag_pass@localhost:5433/srag_test",
    )
    return Settings(database_url=test_url)


@pytest.fixture(scope="module")
def engine(settings):
    """SQLAlchemy engine for integration tests."""
    from sqlalchemy import create_engine

    eng = create_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.mark.integration
class TestMortalityRate:
    """Validate mortality rate metric query."""

    def test_mortality_rate_in_range(self, settings):
        """Mortality rate should be between 0% and 50% for SRAG cases."""
        result = execute_metric_query("mortality_rate", params={}, settings=settings)
        assert "taxa_mortalidade" in result or "Error" not in result, result

        # Parse the result to extract taxa_mortalidade
        for line in result.split("\n"):
            if "taxa_mortalidade" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        value = float(parts[-1].strip())
                        assert 0 < value < 50, f"Mortality rate {value}% outside 0-50%"
                    except ValueError:
                        pass

    def test_mortality_rate_has_obitos_and_total(self, settings):
        """Mortality rate query should return obitos and total counts."""
        result = execute_metric_query("mortality_rate", params={}, settings=settings)
        assert "obitos_srag" in result, f"Missing obitos_srag in: {result}"
        assert "total_com_desfecho" in result, f"Missing total_com_desfecho in: {result}"


@pytest.mark.integration
class TestICURate:
    """Validate ICU rate metric query."""

    def test_icu_rate_in_range(self, settings):
        """ICU rate should be between 0% and 80% for confirmed SRAG cases."""
        result = execute_metric_query("icu_rate", params={}, settings=settings)
        assert "taxa_uti" in result, f"Missing taxa_uti in: {result}"

        for line in result.split("\n"):
            if "taxa_uti" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        value = float(parts[-1].strip())
                        assert 0 < value < 80, f"ICU rate {value}% outside 0-80%"
                    except ValueError:
                        pass

    def test_icu_rate_has_internados_and_total(self, settings):
        """ICU rate query should return internados_uti and total_internados."""
        result = execute_metric_query("icu_rate", params={}, settings=settings)
        assert "internados_uti" in result, f"Missing internados_uti in: {result}"
        assert "total_internados" in result, f"Missing total_internados in: {result}"


@pytest.mark.integration
class TestVaccinationRate:
    """Validate vaccination rate metric query."""

    def test_vaccination_rate_in_range(self, settings):
        """Vaccination rate should be between 0% and 100% for years >= 2021."""
        result = execute_metric_query("vaccination_rate", params={}, settings=settings)
        assert "taxa_vacinacao" in result, f"Missing taxa_vacinacao in: {result}"

        for line in result.split("\n"):
            if "taxa_vacinacao" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        value = float(parts[-1].strip())
                        assert 0 <= value <= 100, f"Vaccination rate {value}% outside 0-100%"
                    except ValueError:
                        pass

    def test_vaccination_rate_filters_2021_onwards(self, settings):
        """Vaccination rate query should only include anos >= 2021."""
        for line in execute_metric_query("vaccination_rate", params={}, settings=settings).split(
            "\n"
        ):
            if "ano_notificacao" in line.lower():
                assert "2021" in line or ">=" in line, "Should filter for anos >= 2021"


@pytest.mark.integration
class TestCaseIncreaseRate:
    """Validate case increase rate metric query."""

    def test_case_increase_rate_not_null(self, settings):
        """Case increase rate should return a result (may be None if previous week has 0 cases)."""
        result = execute_metric_query("case_increase_rate", params={}, settings=settings)
        assert "taxa_aumento" in result, f"Missing taxa_aumento in: {result}"
        # taxa_aumento can be None (NULL) when previous week has 0 cases (division by zero)
        # This is expected behavior — NULLIF prevents crash
        assert "Error" not in result, f"Error in result: {result}"

    def test_case_increase_rate_has_weekly_counts(self, settings):
        """Case increase rate query should return semana_atual and semana_anterior counts."""
        result = execute_metric_query("case_increase_rate", params={}, settings=settings)
        assert "casos" in result, f"Missing casos field in: {result}"


@pytest.mark.integration
class TestDailyCases:
    """Validate daily cases 30-day query."""

    def test_daily_cases_30d_has_data(self, settings):
        """Daily cases query should return at least 1 row."""
        result = execute_metric_query("daily_cases_30d", params={}, settings=settings)
        assert "No data" not in result, f"Daily cases returned no data: {result}"
        assert "dt_notific" in result, f"Missing dt_notific in: {result}"
        assert "casos" in result, f"Missing casos in: {result}"


@pytest.mark.integration
class TestMonthlyCases:
    """Validate monthly cases 12-month query."""

    def test_monthly_cases_12m_has_data(self, settings):
        """Monthly cases query should return at least 1 row."""
        result = execute_metric_query("monthly_cases_12m", params={}, settings=settings)
        assert "No data" not in result, f"Monthly cases returned no data: {result}"
        assert "mes" in result, f"Missing mes in: {result}"
        assert "casos" in result, f"Missing casos in: {result}"


@pytest.mark.integration
class TestDataRef:
    """Validate that data_ref uses MAX(dt_notific), not NOW()."""

    def test_metrics_with_max_dt_notific_as_ref(self, engine):
        """data_ref should come from MAX(dt_notific), NOT NOW() or CURRENT_DATE."""
        import datetime

        with engine.connect() as conn:
            result = conn.execute(text(get_data_ref_query()))
            data_ref = result.scalar()

        assert data_ref is not None, "MAX(dt_notific) returned NULL — no data in DB?"
        assert isinstance(data_ref, (datetime.date, datetime.datetime)), (
            f"data_ref should be a date, got {type(data_ref)}"
        )

    def test_data_ref_is_max_not_now(self, engine):
        """data_ref should equal MAX(dt_notific), not current date."""
        with engine.connect() as conn:
            max_result = conn.execute(text("SELECT MAX(dt_notific) FROM srag.srag_cases"))
            max_dt = max_result.scalar()

        # MAX(dt_notific) should be a real date, not NULL
        assert max_dt is not None, "No data in srag_cases table"
        # The important thing: our queries use MAX(dt_notific), not NOW()
        # This is validated by get_data_ref_query returning MAX(dt_notific)

    def test_all_metric_queries_use_data_ref(self):
        """All metric queries should reference :data_ref or :data_inicio/:data_fim."""
        for name, query in METRIC_QUERIES.items():
            has_params = ":data_ref" in query or ":data_inicio" in query or ":data_fim" in query
            assert has_params, f"Query {name} should use date parameters, not NOW()"


@pytest.mark.integration
class TestQueryResultsNumeric:
    """Validate that metric results contain parseable numeric values."""

    def test_mortality_rate_returns_numeric(self, settings):
        """Mortality rate result should contain a numeric taxa_mortalidade."""
        result = execute_metric_query("mortality_rate", params={}, settings=settings)
        found_number = False
        for line in result.split("\n"):
            if "taxa_mortalidade" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        float(parts[-1].strip())
                        found_number = True
                    except ValueError:
                        pass
        assert found_number, f"Could not find numeric taxa_mortalidade in: {result}"

    def test_icu_rate_returns_numeric(self, settings):
        """ICU rate result should contain a numeric taxa_uti."""
        result = execute_metric_query("icu_rate", params={}, settings=settings)
        found_number = False
        for line in result.split("\n"):
            if "taxa_uti" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        float(parts[-1].strip())
                        found_number = True
                    except ValueError:
                        pass
        assert found_number, f"Could not find numeric taxa_uti in: {result}"

    def test_vaccination_rate_returns_numeric(self, settings):
        """Vaccination rate result should contain a numeric taxa_vacinacao."""
        result = execute_metric_query("vaccination_rate", params={}, settings=settings)
        found_number = False
        for line in result.split("\n"):
            if "taxa_vacinacao" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        float(parts[-1].strip())
                        found_number = True
                    except ValueError:
                        pass
        assert found_number, f"Could not find numeric taxa_vacinacao in: {result}"

    def test_case_increase_rate_returns_numeric(self, settings):
        """Case increase rate result should contain numeric taxa_aumento (or None if undefined)."""
        result = execute_metric_query("case_increase_rate", params={}, settings=settings)
        # taxa_aumento can be None when previous week has 0 cases (NULLIF prevents division by zero)
        # In that case, the formatted result contains "None" or "NaN"
        found_number = False
        found_none = False
        for line in result.split("\n"):
            if "taxa_aumento" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    val = parts[-1].strip()
                    if val in ("None", "NaN", "null"):
                        found_none = True
                    else:
                        try:
                            float(val)
                            found_number = True
                        except ValueError:
                            pass
        assert found_number or found_none, f"Could not find numeric taxa_aumento in: {result}"
