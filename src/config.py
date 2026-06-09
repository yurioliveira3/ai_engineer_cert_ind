from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://srag_app:srag_pass@db:5432/srag"
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dim: int = 1024
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def effective_api_key(self) -> str:
        """Return the API key to use.

        For Gemini, falls back to GOOGLE_API_KEY if LLM_API_KEY is empty.
        """
        if self.llm_api_key and self.llm_api_key != "placeholder":
            return self.llm_api_key
        import os

        return os.environ.get("GOOGLE_API_KEY", "")
