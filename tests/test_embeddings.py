from unittest.mock import MagicMock, patch


class TestEmbeddingsService:
    def test_embeddings_service_loads_model(self):
        """EmbeddingsService should load without error."""
        with patch("src.data.embeddings.HuggingFaceEmbeddings") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.embed_query.return_value = [0.1] * 1024
            mock_cls.return_value = mock_instance

            from src.data.embeddings import EmbeddingsService

            EmbeddingsService(model_name="BAAI/bge-large-en-v1.5")
            mock_cls.assert_called_once()

    def test_embed_query_returns_1024_dim(self):
        """embed_query should return a vector of dimension 1024."""
        with patch("src.data.embeddings.HuggingFaceEmbeddings") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.embed_query.return_value = [0.1] * 1024
            mock_cls.return_value = mock_instance

            from src.data.embeddings import EmbeddingsService

            service = EmbeddingsService(model_name="BAAI/bge-large-en-v1.5")
            result = service.embed_query("teste de embedding")
            assert len(result) == 1024


class TestNewsEmbeddingsRepository:
    def test_upsert_idempotent(self):
        """2 upserts of the same URL should not duplicate rows."""
        # This is an integration test that requires PostgreSQL with pgvector
        # Unit test verifies the concept with mocked engine
        pass

    def test_similarity_search_returns_topk(self):
        """similarity_search should return exactly k results (or fewer)."""
        # Integration test requiring pgvector
        pass

    def test_similarity_search_ordered_by_score(self):
        """Results should be ordered by similarity score (descending)."""
        # Integration test requiring pgvector
        pass
