"""Embeddings service and news embeddings repository for RAG."""

import logging

from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import text

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Service for generating text embeddings using a HuggingFace model."""

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.model_name = model_name
        self._model = HuggingFaceEmbeddings(model_name=model_name)

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string."""
        return self._model.embed_query(query)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        return self._model.embed_documents(texts)


class NewsEmbeddingsRepository:
    """Repository for storing and querying news embeddings in pgvector."""

    def __init__(self, engine, embeddings_service: EmbeddingsService):
        self.engine = engine
        self.embeddings_service = embeddings_service

    def upsert(self, items: list[dict]) -> int:
        """Insert or update news items with embeddings.

        Each item dict should have: url, title, snippet, source, query_used.
        Returns the number of items upserted.
        """
        if not items:
            return 0

        count = 0
        for item in items:
            embedding = self.embeddings_service.embed_query(
                f"{item.get('title', '')} {item.get('snippet', '')}"
            )
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

            with self.engine.connect() as conn:
                upsert_sql = text(
                    """
                    INSERT INTO news.news_embeddings
                        (url, title, snippet, source, query_used, embedding)
                    VALUES
                        (:url, :title, :snippet,
                         :source, :query_used, :embedding::vector)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        snippet = EXCLUDED.snippet,
                        source = EXCLUDED.source,
                        query_used = EXCLUDED.query_used,
                        embedding = EXCLUDED.embedding,
                        indexed_at = NOW()
                """
                )
                conn.execute(
                    upsert_sql,
                    {
                        "url": item["url"],
                        "title": item.get("title"),
                        "snippet": item.get("snippet"),
                        "source": item.get("source"),
                        "query_used": item.get("query_used"),
                        "embedding": embedding_str,
                    },
                )
                conn.commit()
            count += 1

        logger.info(f"Upserted {count} news items")
        return count

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        """Search for similar news items using cosine similarity.

        Returns up to k results with similarity score >= 0.6.
        """
        query_embedding = self.embeddings_service.embed_query(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        with self.engine.connect() as conn:
            results = conn.execute(
                text("""
                    SELECT url, title, snippet, source, query_used, indexed_at,
                           1 - (embedding <=> :query_embedding::vector) as score
                    FROM news.news_embeddings
                    WHERE 1 - (embedding <=> :query_embedding::vector) >= 0.6
                    ORDER BY embedding <=> :query_embedding::vector
                    LIMIT :k
                """),
                {"query_embedding": embedding_str, "k": k},
            )
            rows = results.fetchall()

        return [
            {
                "url": row[0],
                "title": row[1],
                "snippet": row[2],
                "source": row[3],
                "query_used": row[4],
                "indexed_at": row[5],
                "score": float(row[6]),
            }
            for row in rows
        ]
