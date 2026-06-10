# Sampling defaults tuned for factual, grounded analysis (epidemiological data +
# news) rather than creative generation: low temperature with reduced nucleus
# (top_p) and top_k narrow the model to high-probability, on-context tokens.
# top_k applies to Gemini only (not part of the standard OpenAI chat API).
from typing import Any

_FACTUAL_SAMPLING = {"temperature": 0.2, "top_p": 0.85}

PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "class": "ChatGoogleGenerativeAI",
        "default_model": "gemini-2.5-flash",
        "requires_base_url": False,
        "requires_api_key": True,
        "extra_kwargs": {"thinking_budget": 0, **_FACTUAL_SAMPLING, "top_k": 20},
    },
    "openrouter": {
        "class": "ChatOpenAI",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "requires_base_url": False,
        "requires_api_key": True,
        "extra_headers": {"HTTP-Referer": "srag-agent", "X-Title": "SRAG Agent"},
        "extra_kwargs": dict(_FACTUAL_SAMPLING),
    },
    "groq": {
        "class": "ChatOpenAI",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_base_url": False,
        "requires_api_key": True,
        "extra_kwargs": dict(_FACTUAL_SAMPLING),
    },
    "ollama": {
        "class": "ChatOpenAI",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "requires_base_url": False,
        "requires_api_key": False,
        "extra_kwargs": dict(_FACTUAL_SAMPLING),
    },
}


def get_sampling_params(provider: str) -> dict:
    """Return the sampling params (temperature/top_p/top_k) for a provider.

    Only the keys actually configured are returned (top_k applies to Gemini
    only). Used by the UI to display the active generation settings.
    """
    extra = PROVIDERS.get(provider, {}).get("extra_kwargs", {})
    return {k: extra[k] for k in ("temperature", "top_p", "top_k") if k in extra}
