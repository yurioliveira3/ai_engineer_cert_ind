"""News search tool with DuckDuckGo and pgvector semantic search."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from langchain_community.tools import DuckDuckGoSearchResults

from src.config import Settings

if TYPE_CHECKING:
    from src.data.embeddings import NewsEmbeddingsRepository

logger = logging.getLogger(__name__)

TRUSTED_DOMAINS = {
    "gov.br",
    "fiocruz.br",
    "who.int",
    "saude.gov.br",
    "paho.org",
    "g1.globo.com",
    "folha.uol.com.br",
}


def _classify_source(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    for domain in TRUSTED_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return "trusted"
    return "unverified"


def _parse_ddg_results(raw, query: str) -> list[dict]:
    # DuckDuckGoSearchResults(output_format="list") returns a list of dicts;
    # older/mocked callers may pass a JSON string.
    if isinstance(raw, str):
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            items = []
    else:
        items = raw or []

    if isinstance(items, dict):
        items = [items]

    results: list[dict] = []
    for item in items:
        url = item.get("link", "")
        if not url:
            continue
        results.append(
            {
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("snippet", ""),
                "source": _classify_source(url),
                "published_at": None,
                "query_used": query,
            }
        )
    return results


def _make_repo(settings):
    from sqlalchemy import create_engine

    from src.data.embeddings import EmbeddingsService, NewsEmbeddingsRepository

    # TODO: EmbeddingsService is instantiated once here (search_and_index_news) and
    # again in semantic_search_news, causing the model to load from disk twice per run
    # (~6s overhead). Future improvement: create a single shared instance in
    # create_agent() and inject it into both steps.
    engine = create_engine(settings.database_url)
    emb_service = EmbeddingsService(model_name=settings.embedding_model)
    return NewsEmbeddingsRepository(engine, emb_service)


def search_and_index_news(
    query: str,
    max_results: int = 5,
    repo: NewsEmbeddingsRepository | None = None,
    settings: Settings | None = None,
) -> list[dict]:
    """Search DuckDuckGo for SRAG-related news and index results in pgvector.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (1-5).
        repo: Optional NewsEmbeddingsRepository instance.
        settings: Optional Settings instance.

    Returns:
        List of dicts with title, url, snippet, source, published_at, query_used.

    Raises:
        ValueError: If max_results exceeds the allowed maximum.
    """
    if max_results > 5:
        raise ValueError(f"max_results={max_results} exceeds maximum of 5")

    ddg = DuckDuckGoSearchResults(  # type: ignore[call-arg]
        max_results=max_results, region="br-pt", output_format="list"
    )
    raw = ddg.invoke(query)

    results = _parse_ddg_results(raw, query)
    logger.info(f"DuckDuckGo returned {len(results)} results for query='{query}'")

    if repo is not None:
        repo.upsert(results)
    elif settings is not None:
        auto_repo = _make_repo(settings)
        auto_repo.upsert(results)

    return results


def semantic_search_news(
    query: str,
    k: int = 3,
    repo: NewsEmbeddingsRepository | None = None,
    settings: Settings | None = None,
) -> list[dict]:
    """Search indexed news using pgvector similarity search.

    Args:
        query: Search query string to find semantically similar news.
        k: Number of results to return.
        repo: Optional NewsEmbeddingsRepository instance.
        settings: Optional Settings instance used when repo is not provided.

    Returns:
        List of dicts with matching news articles.
    """
    if repo is None:
        effective_settings = settings or Settings()
        repo = _make_repo(effective_settings)

    return repo.similarity_search(query, k)
