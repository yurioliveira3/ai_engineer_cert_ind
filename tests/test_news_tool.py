from unittest.mock import MagicMock, patch


class TestSearchReturnsResults:
    def test_search_returns_results(self):
        """search_and_index_news returns non-empty list with title, url, snippet."""
        with patch("src.agent.tools.news_tool.DuckDuckGoSearchResults") as mock_ddg_cls:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = (
                '[{"snippet": "Dengue cases rise", "title": "Dengue SP", '
                '"link": "https://g1.globo.com/dengue"}, '
                '{"snippet": "Fiocruz alert", "title": "Alerta Fiocruz", '
                '"link": "https://fiocruz.br/alerta"}]'
            )
            mock_ddg_cls.return_value = mock_instance

            from src.agent.tools.news_tool import search_and_index_news

            results = search_and_index_news("dengue", max_results=2)

            assert len(results) == 2
            for item in results:
                assert "title" in item
                assert "url" in item
                assert "snippet" in item
                assert "source" in item

    def test_search_classifies_trusted_source(self):
        """URLs from TRUSTED_DOMAINS get source='trusted'."""
        with patch("src.agent.tools.news_tool.DuckDuckGoSearchResults") as mock_ddg_cls:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = (
                '[{"snippet": "s1", "title": "t1", '
                '"link": "https://www.gov.br/saude/noticia"}, '
                '{"snippet": "s2", "title": "t2", '
                '"link": "https://blog.example.com/post"}]'
            )
            mock_ddg_cls.return_value = mock_instance

            from src.agent.tools.news_tool import search_and_index_news

            results = search_and_index_news("saude")
            trusted = [r for r in results if r["source"] == "trusted"]
            unverified = [r for r in results if r["source"] == "unverified"]
            assert len(trusted) == 1
            assert len(unverified) == 1


class TestSearchIndexesInPgvector:
    def test_search_indexes_in_pgvector(self):
        """After search_and_index_news, repo.upsert is called with results."""
        with patch("src.agent.tools.news_tool.DuckDuckGoSearchResults") as mock_ddg_cls:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = (
                '[{"snippet": "s1", "title": "t1", "link": "https://who.int/page"}]'
            )
            mock_ddg_cls.return_value = mock_instance

            mock_repo = MagicMock()
            mock_repo.upsert.return_value = 1

            from src.agent.tools.news_tool import search_and_index_news

            search_and_index_news("covid", repo=mock_repo)

            mock_repo.upsert.assert_called_once()
            upsert_args = mock_repo.upsert.call_args[0][0]
            assert len(upsert_args) == 1
            assert upsert_args[0]["url"] == "https://who.int/page"
            assert upsert_args[0]["query_used"] == "covid"


class TestSearchUpsertIsIdempotent:
    def test_search_upsert_is_idempotent(self):
        """Running twice with same query doesn't duplicate (SQL ON CONFLICT)."""
        with patch("src.agent.tools.news_tool.DuckDuckGoSearchResults") as mock_ddg_cls:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = (
                '[{"snippet": "s1", "title": "t1", "link": "https://who.int/page"}]'
            )
            mock_ddg_cls.return_value = mock_instance

            mock_repo = MagicMock()
            mock_repo.upsert.return_value = 1

            from src.agent.tools.news_tool import search_and_index_news

            search_and_index_news("covid", repo=mock_repo)
            search_and_index_news("covid", repo=mock_repo)

            assert mock_repo.upsert.call_count == 2
            first_items = mock_repo.upsert.call_args_list[0][0][0]
            second_items = mock_repo.upsert.call_args_list[1][0][0]
            assert first_items[0]["url"] == second_items[0]["url"]


class TestSemanticSearchReturnsTopk:
    def test_semantic_search_returns_topk(self):
        """semantic_search_news returns up to k results."""
        mock_repo = MagicMock()
        mock_results = [
            {
                "url": f"https://example.com/{i}",
                "title": f"t{i}",
                "snippet": f"s{i}",
                "score": 0.9 - i * 0.1,
            }
            for i in range(3)
        ]
        mock_repo.similarity_search.return_value = mock_results

        from src.agent.tools.news_tool import semantic_search_news

        results = semantic_search_news("dengue", k=3, repo=mock_repo)

        assert len(results) == 3
        mock_repo.similarity_search.assert_called_once_with("dengue", 3)


class TestSemanticSearchWithoutRepoCreatesDefault:
    def test_semantic_search_without_repo_creates_default(self):
        """When no repo provided, creates one from settings."""
        with patch("src.agent.tools.news_tool._make_repo") as mock_make_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.similarity_search.return_value = [
                {
                    "url": "https://example.com/1",
                    "title": "t1",
                    "snippet": "s1",
                    "score": 0.85,
                }
            ]
            mock_make_repo.return_value = mock_repo_instance

            from src.agent.tools.news_tool import semantic_search_news

            results = semantic_search_news("dengue", k=1)

            assert len(results) == 1
            mock_make_repo.assert_called_once()
