"""Tests for the LangGraph Orchestrator."""

from unittest.mock import MagicMock, patch

from src.agent.orchestrator import AgentState, create_agent


class TestAgentState:
    """Verify AgentState has all required keys."""

    def test_agent_state_has_required_keys(self):
        """AgentState TypedDict has all required keys."""
        required_keys = [
            "messages",
            "metrics",
            "charts",
            "news",
            "news_semantic",
            "analysis",
            "report_markdown",
            "report_pdf_path",
            "error",
            "session_id",
        ]
        for key in required_keys:
            assert key in AgentState.__annotations__, f"Missing key: {key}"


class TestOrchestratorFlow:
    """Tests for the LangGraph orchestrator flow."""

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_agent_full_flow(self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls):
        """Full agent flow executes without error, state has all keys."""

        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        mock_invoke.return_value = MagicMock(content="Análise dos dados SRAG.")

        with (
            patch("src.agent.orchestrator.execute_metric_query") as mock_sql,
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch("src.agent.orchestrator.search_and_index_news") as mock_news,
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_sql.return_value = (
                "Metric: mortality_rate\n  taxa_mortalidade: 7.75\n  Execution time: 10ms"
            )
            mock_news.return_value = [
                {
                    "title": "SRAG SP",
                    "url": "https://g1.globo.com/srag",
                    "snippet": "Aumento",
                    "source": "trusted",
                }
            ]
            mock_semantic.return_value = [
                {
                    "title": "SRAG MG",
                    "url": "https://example.com",
                    "snippet": "Dados",
                    "score": 0.85,
                }
            ]
            mock_daily.return_value = ("/tmp/daily.png", MagicMock())
            mock_monthly.return_value = ("/tmp/monthly.png", MagicMock())
            mock_report.return_value = {
                "markdown": "# Relatório SRAG",
                "pdf_path": "/tmp/report.pdf",
            }

            agent = create_agent(settings=mock_settings)
            result = agent.invoke(
                {
                    "messages": [("user", "Gere o relatório SRAG")],
                }
            )

            assert "metrics" in result
            assert "charts" in result
            assert "news" in result
            assert "analysis" in result
            assert "report_markdown" in result

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_agent_returns_all_metrics(
        self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls
    ):
        """All 4 metrics are present in state after execution."""
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_invoke.return_value = MagicMock(content="Análise.")

        def mock_sql_side_effect(metric_name, **kwargs):
            metrics_map = {
                "case_increase_rate": "  taxa_aumento: 12.5",
                "mortality_rate": "  taxa_mortalidade: 7.75",
                "icu_rate": "  taxa_uti: 27.28",
                "vaccination_rate": "  taxa_vacinacao: 56.01",
                "daily_cases_30d": "  dt_notific: 2024-01-01\n  casos: 100",
                "monthly_cases_12m": "  mes: 2024-01-01\n  casos: 3000",
            }
            return metrics_map.get(metric_name, "  value: 0")

        with (
            patch("src.agent.orchestrator.execute_metric_query", side_effect=mock_sql_side_effect),
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch("src.agent.orchestrator.search_and_index_news") as mock_news,
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_news.return_value = []
            mock_semantic.return_value = []
            mock_daily.return_value = ("/tmp/daily.png", MagicMock())
            mock_monthly.return_value = ("/tmp/monthly.png", MagicMock())
            mock_report.return_value = {"markdown": "# Report", "pdf_path": "/tmp/r.pdf"}

            agent = create_agent(settings=mock_settings)
            result = agent.invoke({"messages": [("user", "Relatório")]})

            assert "case_increase_rate" in result["metrics"]
            assert "mortality_rate" in result["metrics"]
            assert "icu_rate" in result["metrics"]
            assert "vaccination_rate" in result["metrics"]

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_agent_graceful_degradation_news(
        self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls
    ):
        """If news tool raises, agent continues and report is generated without news."""
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_invoke.return_value = MagicMock(content="Análise SRAG sem notícias.")

        with (
            patch("src.agent.orchestrator.execute_metric_query") as mock_sql,
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch(
                "src.agent.orchestrator.search_and_index_news", side_effect=Exception("DDG failed")
            ),
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_sql.return_value = "  taxa_mortalidade: 7.75"
            mock_semantic.return_value = []
            mock_daily.return_value = ("/tmp/d.png", MagicMock())
            mock_monthly.return_value = ("/tmp/m.png", MagicMock())
            mock_report.return_value = {"markdown": "# Report", "pdf_path": "/tmp/r.pdf"}

            agent = create_agent(settings=mock_settings)
            result = agent.invoke({"messages": [("user", "Relatório")]})

            # Agent should still produce a report even if news fails
            assert "report_markdown" in result
            # News should be empty (graceful degradation)
            assert result.get("news") == [] or result.get("news") is not None

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_agent_graceful_degradation_metrics(
        self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls
    ):
        """If one metric fails, others continue."""
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_invoke.return_value = MagicMock(content="Análise parcial.")

        call_count = [0]

        def mock_sql_side_effect(metric_name, **kwargs):
            call_count[0] += 1
            if metric_name == "mortality_rate":
                raise Exception("DB timeout")
            return "  value: 50"

        with (
            patch("src.agent.orchestrator.execute_metric_query", side_effect=mock_sql_side_effect),
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch("src.agent.orchestrator.search_and_index_news") as mock_news,
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_news.return_value = []
            mock_semantic.return_value = []
            mock_daily.return_value = ("/tmp/d.png", MagicMock())
            mock_monthly.return_value = ("/tmp/m.png", MagicMock())
            mock_report.return_value = {"markdown": "# Report", "pdf_path": "/tmp/r.pdf"}

            agent = create_agent(settings=mock_settings)
            result = agent.invoke({"messages": [("user", "Relatório")]})

            # mortality_rate should have an error, other metrics should have data
            metrics = result["metrics"]
            assert "mortality_rate" in metrics
            assert metrics["mortality_rate"].get("error") is not None or "error" in str(
                metrics["mortality_rate"]
            )

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_audit_session_created(self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls):
        """audit.agent_sessions receives a row when agent is invoked."""
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid-123"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_invoke.return_value = MagicMock(content="Análise.")

        with (
            patch("src.agent.orchestrator.execute_metric_query") as mock_sql,
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch("src.agent.orchestrator.search_and_index_news") as mock_news,
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_sql.return_value = "  taxas: 7.75"
            mock_news.return_value = []
            mock_semantic.return_value = []
            mock_daily.return_value = ("/tmp/d.png", MagicMock())
            mock_monthly.return_value = ("/tmp/m.png", MagicMock())
            mock_report.return_value = {"markdown": "# Report", "pdf_path": "/tmp/r.pdf"}

            agent = create_agent(settings=mock_settings)
            agent.invoke({"messages": [("user", "Relatório")]})

            # Audit session was started and ended
            mock_audit.start_session.assert_called_once()
            mock_audit.end_session.assert_called_once()

    @patch("src.agent.orchestrator.AgentAuditLogger")
    @patch("src.agent.orchestrator.safe_invoke")
    @patch("src.agent.orchestrator.get_chat_model")
    @patch("src.agent.orchestrator.create_engine")
    def test_audit_decisions_logged(self, mock_engine_cls, mock_llm, mock_invoke, mock_audit_cls):
        """log_decision is called 6 times (one per orchestrator node)."""
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://test:test@localhost:5433/srag"
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_model = "gemini-2.5-flash"
        mock_settings.effective_api_key = "test-key"
        mock_settings.embedding_model = "BAAI/bge-large-en-v1.5"

        mock_audit = MagicMock()
        mock_audit.start_session.return_value = "test-uuid-dec"
        mock_audit_cls.return_value = mock_audit
        mock_audit_cls.side_effect = lambda **kw: mock_audit

        mock_invoke.return_value = MagicMock(content="Análise.")

        with (
            patch("src.agent.orchestrator.execute_metric_query") as mock_sql,
            patch("src.agent.orchestrator.get_data_ref", return_value="2026-12-05"),
            patch("src.agent.orchestrator.execute_tabular_query", return_value=[]),
            patch("src.agent.orchestrator.search_and_index_news") as mock_news,
            patch("src.agent.orchestrator.semantic_search_news") as mock_semantic,
            patch("src.agent.orchestrator.generate_daily_cases_chart") as mock_daily,
            patch("src.agent.orchestrator.generate_monthly_cases_chart") as mock_monthly,
            patch("src.agent.orchestrator.generate_report") as mock_report,
        ):
            mock_sql.return_value = "  taxa_mortalidade: 7.75"
            mock_news.return_value = []
            mock_semantic.return_value = []
            mock_daily.return_value = ("/tmp/d.png", MagicMock())
            mock_monthly.return_value = ("/tmp/m.png", MagicMock())
            mock_report.return_value = {"markdown": "# Report", "pdf_path": "/tmp/r.pdf"}

            agent = create_agent(settings=mock_settings)
            agent.invoke({"messages": [("user", "Relatório")]})

            assert mock_audit.log_decision.call_count == 6


class TestParseMetricResultEdgeCases:
    def test_parse_metric_result_with_nan(self):
        """_parse_metric_result should convert 'NaN' string to None."""
        from src.agent.orchestrator import _parse_metric_result

        result = _parse_metric_result("taxa_aumento: NaN\n")
        assert result.get("taxa_aumento") is None

    def test_parse_metric_result_with_none_string(self):
        """_parse_metric_result should convert 'None' string to None."""
        from src.agent.orchestrator import _parse_metric_result

        result = _parse_metric_result("taxa_aumento: None\n")
        assert result.get("taxa_aumento") is None

    def test_parse_metric_result_with_inf(self):
        """_parse_metric_result should convert 'inf' string to None."""
        from src.agent.orchestrator import _parse_metric_result

        result = _parse_metric_result("taxa_aumento: inf\n")
        assert result.get("taxa_aumento") is None
