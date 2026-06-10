"""Tests for LLM provider configuration helpers."""

from src.llm.providers import get_sampling_params


class TestGetSamplingParams:
    def test_gemini_has_temperature_top_p_top_k(self):
        """Gemini exposes the three sampling knobs (top_k included)."""
        params = get_sampling_params("gemini")
        assert params == {"temperature": 0.2, "top_p": 0.85, "top_k": 20}

    def test_openai_compatible_has_no_top_k(self):
        """OpenAI-compatible providers omit top_k (not in the standard API)."""
        params = get_sampling_params("groq")
        assert params == {"temperature": 0.2, "top_p": 0.85}
        assert "top_k" not in params

    def test_unknown_provider_returns_empty(self):
        assert get_sampling_params("nonexistent") == {}

    def test_thinking_budget_not_exposed(self):
        """Only sampling knobs are returned, not internal extra_kwargs."""
        assert "thinking_budget" not in get_sampling_params("gemini")
