import logging
import time

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from src.config import Settings
from src.llm.providers import PROVIDERS

logger = logging.getLogger(__name__)

_embeddings_instance: HuggingFaceEmbeddings | None = None


def get_chat_model(settings: Settings):
    """Dispatch LLM provider based on settings. Returns a BaseChatModel instance."""
    provider_key = settings.llm_provider.lower()
    if provider_key not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider: {provider_key}. Available: {', '.join(PROVIDERS.keys())}"
        )

    provider = PROVIDERS[provider_key]
    model_name = settings.llm_model or provider.get("default_model", "")
    api_key = settings.effective_api_key

    if provider["class"] == "ChatGoogleGenerativeAI":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            **provider.get("extra_kwargs", {}),
        )

    if provider["class"] == "ChatOpenAI":
        kwargs: dict = {
            "model": model_name,
            "api_key": api_key if provider.get("requires_api_key", True) else "ollama",
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        elif "base_url" in provider:
            kwargs["base_url"] = provider["base_url"]

        if "extra_headers" in provider:
            kwargs["default_headers"] = provider["extra_headers"]

        kwargs.update(provider.get("extra_kwargs", {}))

        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported provider class: {provider['class']}")


def get_embeddings(settings: Settings) -> HuggingFaceEmbeddings:
    """Return a singleton HuggingFaceEmbeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
        )
        logger.info("Embedding model loaded")
    return _embeddings_instance


_RATE_LIMIT_MARKERS = ["429", "ResourceExhausted", "RateLimitError", "rate_limit"]


def _is_rate_limit_error(error: Exception) -> bool:
    error_str = str(error).lower()
    return any(marker.lower() in error_str for marker in _RATE_LIMIT_MARKERS)


def safe_invoke(model, prompt: str, retries: int = 5, backoff_factor: int = 2):
    """Invoke LLM with retry on rate-limit errors. Uses exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return model.invoke([HumanMessage(content=prompt)])
        except Exception as e:
            last_error = e
            if not _is_rate_limit_error(e):
                raise
            if attempt < retries:
                wait = backoff_factor ** (attempt + 1)
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{retries}), retrying in {wait}s..."
                )
                time.sleep(wait)

    if last_error is not None:
        raise last_error
    raise RuntimeError("safe_invoke: no result and no error captured")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) used as a fallback."""
    return max(1, len(text) // 4) if text else 0


def get_token_usage(response, prompt: str = "") -> tuple[int, int]:
    """Return ``(input_tokens, output_tokens)`` for an LLM response.

    Prefers the provider-reported ``usage_metadata`` (exact token counts, e.g.
    from Gemini). Falls back to a ~4-chars-per-token estimate for whichever
    side the provider does not report.
    """
    usage = getattr(response, "usage_metadata", None) or {}
    tokens_in = int(usage.get("input_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or 0)

    if not tokens_in:
        tokens_in = _estimate_tokens(prompt)
    if not tokens_out:
        tokens_out = _estimate_tokens(getattr(response, "content", "") or "")

    return tokens_in, tokens_out
