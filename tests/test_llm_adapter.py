from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.config import Settings
from src.llm.adapter import get_chat_model, get_embeddings, safe_invoke


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


class TestGetEmbeddings:
    def test_get_embeddings_returns_singleton(self):
        settings = Settings(embedding_model="BAAI/bge-large-en-v1.5")
        with patch("src.llm.adapter.HuggingFaceEmbeddings") as mock_cls:
            mock_cls.return_value = MagicMock()
            emb1 = get_embeddings(settings)
            emb2 = get_embeddings(settings)
            assert emb1 is emb2


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
