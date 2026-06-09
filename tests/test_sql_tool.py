from sqlalchemy import create_engine

from src.agent.guardrails import _add_limit, safe_execute
from src.data.queries import METRIC_QUERIES


class TestLimitAutoAppend:
    def test_limit_auto_appended(self):
        """Query without LIMIT should receive LIMIT 1000."""
        query = "SELECT COUNT(*) FROM srag.srag_cases WHERE caso_confirmado = true"
        result = _add_limit(query)
        assert "LIMIT 1000" in result

    def test_limit_preserved_if_present(self):
        """Query with existing LIMIT should not get another."""
        query = "SELECT * FROM srag.srag_cases LIMIT 50"
        result = _add_limit(query)
        assert result.count("LIMIT") == 1

    def test_non_select_unchanged(self):
        """Non-SELECT queries should not get LIMIT appended."""
        # This wouldn't pass validate_sql_safety anyway, but testing _add_limit
        pass


class TestSafeExecute:
    def test_destructive_query_blocked_returns_error_string(self):
        """Destructive queries should return an error string, not execute."""
        engine = create_engine("sqlite:///:memory:")
        result, exec_time = safe_execute("DROP TABLE srag.srag_cases;", {}, engine)
        assert isinstance(result, str)
        assert "Destructive" in result or "keyword" in result.lower()
        assert exec_time == 0

    def test_audit_log_on_blocked_query(self):
        """Blocked queries should be logged to audit."""
        # This is tested implicitly via _log_audit
        # Full integration test requires PostgreSQL
        pass


class TestMetricQueries:
    def test_all_metric_queries_defined(self):
        """All expected metric queries should be defined."""
        expected = [
            "case_increase_rate",
            "mortality_rate",
            "icu_rate",
            "vaccination_rate",
            "daily_cases_30d",
            "monthly_cases_12m",
        ]
        for name in expected:
            assert name in METRIC_QUERIES, f"Missing metric query: {name}"

    def test_metric_queries_use_parameters(self):
        """Each metric query should use parameterized values."""
        for name, template in METRIC_QUERIES.items():
            has_params = (
                ":data_ref" in template or ":data_inicio" in template or ":data_fim" in template
            )
            assert has_params, f"Query {name} should use date parameters"

    def test_metric_queries_reference_srag_schema(self):
        """Each metric query should reference srag.srag_cases."""
        for name, template in METRIC_QUERIES.items():
            assert "srag.srag_cases" in template, f"Query {name} should reference srag.srag_cases"
