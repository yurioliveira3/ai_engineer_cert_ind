PROVIDERS = {
    "gemini": {
        "class": "ChatGoogleGenerativeAI",
        "default_model": "gemini-2.5-flash",
        "requires_base_url": False,
        "requires_api_key": True,
        "extra_kwargs": {"thinking_budget": 0},
    },
    "openrouter": {
        "class": "ChatOpenAI",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "requires_base_url": False,
        "requires_api_key": True,
        "extra_headers": {"HTTP-Referer": "srag-agent", "X-Title": "SRAG Agent"},
    },
    "groq": {
        "class": "ChatOpenAI",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_base_url": False,
        "requires_api_key": True,
    },
    "ollama": {
        "class": "ChatOpenAI",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "requires_base_url": False,
        "requires_api_key": False,
    },
}
