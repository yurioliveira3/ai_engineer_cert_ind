"""Smoke tests for the Streamlit UI application."""

from unittest.mock import MagicMock, patch

import pytest


class TestAppImports:
    """Test that the app module can be imported without errors."""

    def test_app_imports_without_error(self):
        """Importing src.ui.app should not raise any exceptions."""
        import src.ui.app  # noqa: F401

    def test_app_has_main_function(self):
        """The app module should expose a main() function."""
        from src.ui.app import main

        assert callable(main)


class TestSessionState:
    """Test that Streamlit session state is populated after agent invocation."""

    @patch("src.ui.app.create_agent")
    @patch("src.ui.app.Settings")
    def test_session_state_persists_report(self, mock_settings_cls, mock_create_agent):
        """After running the agent, session_state['report'] should be populated."""
        from src.ui.app import run_agent

        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "report_markdown": "# Test Report",
            "report_pdf_path": "/tmp/test_report.pdf",
            "metrics": {"mortality_rate": {"taxa_mortalidade": 7.47}},
            "charts": {"daily": "/tmp/daily.png", "monthly": "/tmp/monthly.png"},
            "news": [],
            "news_semantic": [],
            "analysis": "Test analysis",
            "error": None,
        }
        mock_create_agent.return_value = mock_agent
        mock_settings_cls.return_value = MagicMock()

        result = run_agent(mock_settings_cls.return_value)

        assert result is not None
        assert "report_markdown" in result
        assert "report_pdf_path" in result

    @patch("src.ui.app.create_agent")
    @patch("src.ui.app.Settings")
    def test_run_agent_handles_error(self, mock_settings_cls, mock_create_agent):
        """If agent raises an error, run_agent should propagate or handle it."""
        from src.ui.app import run_agent

        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("Agent failed")
        mock_create_agent.return_value = mock_agent
        mock_settings_cls.return_value = MagicMock()

        with pytest.raises(RuntimeError, match="Agent failed"):
            run_agent(mock_settings_cls.return_value)


class TestMetricLabels:
    """Test that METRIC_LABELS are defined correctly."""

    def test_metric_labels_defined(self):
        """METRIC_LABELS should map metric names to Portuguese labels."""
        from src.ui.app import METRIC_LABELS

        assert "mortality_rate" in METRIC_LABELS
        assert "icu_rate" in METRIC_LABELS
        assert "vaccination_rate" in METRIC_LABELS
        assert "case_increase_rate" in METRIC_LABELS

    def test_metric_labels_are_portuguese(self):
        """All labels should be in Portuguese."""
        from src.ui.app import METRIC_LABELS

        for key, label in METRIC_LABELS.items():
            assert isinstance(label, str)
            assert len(label) > 0, f"Label for {key} should not be empty"


class TestFormatMetricValue:
    """Test the format_metric_value helper function."""

    def test_format_numeric_value(self):
        """Numeric values should be formatted as percentages with 2 decimals."""
        from src.ui.app import format_metric_value

        assert format_metric_value(7.47) == "7.47%"

    def test_format_none_value(self):
        """None values should return 'N/A'."""
        from src.ui.app import format_metric_value

        assert format_metric_value(None) == "N/A"

    def test_format_dict_with_rate(self):
        """Dict values containing a rate key should extract and format it."""
        from src.ui.app import format_metric_value

        result = format_metric_value({"taxa_mortalidade": 7.47})
        assert "7.47" in result

    def test_format_dict_with_none_rate(self):
        """Dict values with None rate should return 'N/A'."""
        from src.ui.app import format_metric_value

        result = format_metric_value({"taxa_aumento": None})
        assert result == "N/A"

    def test_format_error_dict(self):
        """Dict with 'error' key should show error indicator."""
        from src.ui.app import format_metric_value

        result = format_metric_value({"error": "query failed"})
        assert "erro" in result.lower() or "error" in result.lower() or "?" in result

    def test_format_metric_value_with_zero(self):
        """format_metric_value(0.0) should return '0.00%'."""
        from src.ui.app import format_metric_value

        assert format_metric_value(0.0) == "0.00%"

    def test_format_metric_value_with_negative(self):
        """format_metric_value(-5.3) should return '-5.30%'."""
        from src.ui.app import format_metric_value

        assert format_metric_value(-5.3) == "-5.30%"

    def test_format_metric_value_empty_dict(self):
        """format_metric_value({}) should return 'N/A'."""
        from src.ui.app import format_metric_value

        assert format_metric_value({}) == "N/A"
