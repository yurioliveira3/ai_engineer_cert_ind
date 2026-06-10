from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.config import Settings
from src.llm.adapter import get_chat_model, safe_invoke


class TestGetChatModel:
    def test_get_chat_model_gemini(self):
        settings = Settings(
            llm_provider="gemini",
            llm_api_key="fake-key",
            llm_model="gemini-2.5-flash",
        )
        with patch("src.llm.adapter.ChatGoogleGenerativeAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model(settings)
            mock_cls.assert_called_once()

    def test_get_chat_model_dispatch(self):
        settings_gemini = Settings(
            llm_provider="gemini",
            llm_api_key="fake-key",
        )
        settings_openrouter = Settings(
            llm_provider="openrouter",
            llm_api_key="fake-key",
        )

        with (
            patch("src.llm.adapter.ChatGoogleGenerativeAI") as mock_gemini,
            patch("src.llm.adapter.ChatOpenAI") as mock_openai,
        ):
            mock_gemini.return_value = MagicMock(name="gemini_model")
            mock_openai.return_value = MagicMock(name="openai_model")

            get_chat_model(settings_gemini)
            get_chat_model(settings_openrouter)

            assert mock_gemini.called
            assert mock_openai.called

    def test_get_chat_model_invalid_provider_raises(self):
        settings = Settings(
            llm_provider="nonexistent_provider",
            llm_api_key="fake-key",
        )
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_chat_model(settings)


class TestSafeInvoke:
    def test_safe_invoke_retries_on_rate_limit(self):
        model = MagicMock()
        error = Exception("429 Resource Exhausted")
        model.invoke.side_effect = [error, AIMessage(content="OK")]

        result = safe_invoke(model, "test prompt", retries=3, backoff_factor=0)
        assert result.content == "OK"
        assert model.invoke.call_count == 2

    def test_safe_invoke_raises_after_max_retries(self):
        model = MagicMock()
        model.invoke.side_effect = Exception("429 Resource Exhausted")

        with pytest.raises(Exception, match="429 Resource Exhausted"):
            safe_invoke(model, "test prompt", retries=2, backoff_factor=0)

        assert model.invoke.call_count == 3  # 1 initial + 2 retries

    def test_safe_invoke_succeeds_first_try(self):
        model = MagicMock()
        model.invoke.return_value = AIMessage(content="Success")

        result = safe_invoke(model, "test prompt")
        assert result.content == "Success"
        assert model.invoke.call_count == 1


class TestGetTokenUsage:
    def test_uses_provider_usage_metadata(self):
        from src.llm.adapter import get_token_usage

        resp = MagicMock()
        resp.usage_metadata = {"input_tokens": 1234, "output_tokens": 567}
        resp.content = "abc"
        assert get_token_usage(resp, "prompt") == (1234, 567)

    def test_falls_back_to_estimate_when_no_metadata(self):
        from src.llm.adapter import get_token_usage

        resp = MagicMock()
        resp.usage_metadata = None
        resp.content = "x" * 400  # ~100 tokens
        # prompt 800 chars -> ~200 tokens; content 400 chars -> ~100 tokens
        assert get_token_usage(resp, "y" * 800) == (200, 100)

    def test_partial_metadata_estimates_missing_side(self):
        from src.llm.adapter import get_token_usage

        resp = MagicMock()
        resp.usage_metadata = {"input_tokens": 50, "output_tokens": 0}
        resp.content = "z" * 40  # ~10 tokens
        tokens_in, tokens_out = get_token_usage(resp, "prompt")
        assert tokens_in == 50
        assert tokens_out == 10
