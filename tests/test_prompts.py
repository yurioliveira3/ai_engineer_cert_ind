"""Tests for prompt loading and rendering."""

import pytest

from src.agent.prompts import load_prompt, render_prompt


class TestPrompts:
    def test_system_prompt_loads(self):
        system = load_prompt("system")
        assert len(system) > 0
        assert "SRAG" in system

    def test_analyze_metrics_injects_news_context(self):
        """Regression: the analyze prompt must render the news context.

        Previously the orchestrator passed news_consolidated but the template
        had no placeholder for it, so the news never reached the LLM.
        """
        rendered, sha = render_prompt(
            "analyze_metrics",
            payload="{'mortality_rate': {'taxa_mortalidade': 7.5}}",
            news_consolidated="- Surto de SRAG (fiocruz.br): alta de casos",
            data_ref="2026-12-05",
            data_hora_consulta="2026-06-11 10:00:00",
        )
        assert "Surto de SRAG" in rendered  # news actually injected
        assert "2026-12-05" in rendered  # data_ref injected
        assert "taxa_mortalidade" in rendered  # payload injected
        assert len(sha) == 64

    def test_missing_prompt_raises(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("does_not_exist")
