"""
Unit Tests for Elasticsearch Modules

Run with: python -m pytest rag_api/tests/test_elastic*.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestElasticConfig:
    """Tests for elastic_config.py"""

    def test_get_es_config_defaults(self):
        """Test default configuration values"""
        from rag_api.elastic_config import (
            ES_HOST, ES_PORT, ES_SCHEME, ES_PASSWORD, ES_INDEX_PREFIX, INDEXES
        )

        assert ES_HOST == "localhost"
        assert ES_PORT == 9200
        assert ES_SCHEME == "http"
        assert ES_INDEX_PREFIX == "graphtalk"
        assert "documents" in INDEXES
        assert "logs" in INDEXES
        assert "queries" in INDEXES
        assert "products" in INDEXES

    def test_index_names_have_prefix(self):
        """Test that all index names have the correct prefix"""
        from rag_api.elastic_config import INDEXES, ES_INDEX_PREFIX

        for key, index_name in INDEXES.items():
            assert index_name.startswith(ES_INDEX_PREFIX)

    def test_documents_mapping_has_required_fields(self):
        """Test documents mapping has all required fields"""
        from rag_api.elastic_config import DOCUMENTS_MAPPING

        properties = DOCUMENTS_MAPPING["mappings"]["properties"]

        assert "doc_id" in properties
        assert "filename" in properties
        assert "content" in properties
        assert "embedding" in properties
        assert properties["embedding"]["type"] == "dense_vector"
        assert properties["embedding"]["dims"] == 384

    def test_get_es_config_returns_dict(self):
        """Test get_es_config returns dictionary"""
        from rag_api.elastic_config import get_es_config

        config = get_es_config()

        assert isinstance(config, dict)
        assert "host" in config
        assert "port" in config
        assert "scheme" in config
        assert "indexes" in config

    def test_get_index_mapping_unknown_index(self):
        """Test get_index_mapping raises for unknown index"""
        from rag_api.elastic_config import get_index_mapping

        with pytest.raises(ValueError) as exc_info:
            get_index_mapping("unknown_index")

        assert "Unknown index" in str(exc_info.value)

    def test_get_index_name_valid_key(self):
        """Test get_index_name returns correct index name"""
        from rag_api.elastic_config import get_index_name, INDEXES

        for key, expected in INDEXES.items():
            result = get_index_name(key)
            assert result == expected

    def test_get_index_name_invalid_key(self):
        """Test get_index_name raises for invalid key"""
        from rag_api.elastic_config import get_index_name

        with pytest.raises(ValueError) as exc_info:
            get_index_name("invalid")

        assert "Unknown index key" in str(exc_info.value)


class TestElasticClient:
    """Tests for elastic_client.py"""

    @pytest.fixture
    def mock_es(self):
        """Create a mock Elasticsearch client"""
        es = AsyncMock()
        es.indices.exists = AsyncMock(return_value=True)
        es.indices.create = AsyncMock()
        es.indices.delete = AsyncMock()
        es.indices.stats = AsyncMock(return_value={
            "indices": {
                "test_index": {
                    "primaries": {
                        "docs": {"count": 100},
                        "store": {"size_in_bytes": 1000}
                    }
                }
            }
        })
        es.indices.refresh = AsyncMock()
        es.index = AsyncMock()
        es.get = AsyncMock(return_value={"_source": {"id": 1}})
        es.delete = AsyncMock()
        es.bulk = AsyncMock(return_value={"errors": False})
        es.search = AsyncMock(return_value={
            "hits": {
                "hits": [{"_source": {"id": 1}}],
                "total": {"value": 1},
                "max_score": 1.0
            }
        })
        es.close = AsyncMock()
        es.info = AsyncMock(return_value={"cluster_name": "test", "version": "8.0"})
        return es

    @pytest.mark.asyncio
    async def test_create_index_already_exists(self, mock_es):
        """Test create_index when index already exists"""
        from rag_api.elastic_client import create_index

        with patch('rag_api.elastic_client.get_es_client', return_value=mock_es):
            result = await create_index("test_index")
            assert result is True
            mock_es.indices.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_index_not_exists(self, mock_es):
        """Test delete_index when index doesn't exist"""
        from rag_api.elastic_client import delete_index

        mock_es.indices.exists = AsyncMock(return_value=False)

        with patch('rag_api.elastic_client.get_es_client', return_value=mock_es):
            result = await delete_index("test_index")
            assert result is True

    @pytest.mark.asyncio
    async def test_index_document(self, mock_es):
        """Test indexing a document"""
        from rag_api.elastic_client import index_document

        with patch('rag_api.elastic_client.get_es_client', return_value=mock_es):
            result = await index_document(
                index_name="test_index",
                doc_id="1",
                document={"content": "test"}
            )
            assert result is True
            mock_es.index.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, mock_es):
        """Test searching documents"""
        from rag_api.elastic_client import search

        with patch('rag_api.elastic_client.get_es_client', return_value=mock_es):
            result = await search(
                index_name="test_index",
                query={"match": {"content": "test"}},
                size=10,
                from_=0
            )
            assert "hits" in result
            assert "total" in result
            assert len(result["hits"]) == 1

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when ES is available"""
        from rag_api.elastic_client import health_check

        result = await health_check()
        if result.get("status") == "connected":
            assert result["cluster_name"] is not None
            assert result["version"] is not None
        else:
            pytest.skip("Elasticsearch not available")


class TestElasticSearch:
    """Tests for elastic_search.py"""

    def test_build_fulltext_query(self):
        """Test building full-text query"""
        from rag_api.elastic_search import build_fulltext_query

        query = build_fulltext_query("test query", fields=["content"])

        assert "bool" in query
        assert "should" in query["bool"]
        assert len(query["bool"]["should"]) > 0

    def test_build_fulltext_query_with_fuzziness(self):
        """Test query has fuzziness settings"""
        from rag_api.elastic_search import build_fulltext_query

        query = build_fulltext_query("test", fuzziness="AUTO")

        multi_match = query["bool"]["should"][0]["multi_match"]
        assert "fuzziness" in multi_match
        assert multi_match["fuzziness"] == "AUTO"

    def test_build_filter_query_empty(self):
        """Test building empty filter query"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query()

        assert "bool" in query
        assert "filter" in query["bool"]
        assert len(query["bool"]["filter"]) == 0

    def test_build_filter_query_with_user_access(self):
        """Test filter query with user access list"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query(user_access=["file1.txt", "file2.txt"])

        filter_clauses = query["bool"]["filter"]
        assert len(filter_clauses) == 1
        assert "terms" in filter_clauses[0]
        assert "filename" in filter_clauses[0]["terms"]

    def test_build_filter_query_with_date_range(self):
        """Test filter query with date range"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query(date_range={
            "from": "2024-01-01",
            "to": "2024-12-31"
        })

        filter_clauses = query["bool"]["filter"]
        range_clause = filter_clauses[0]["range"]["created_at"]
        assert "gte" in range_clause
        assert "lte" in range_clause

    def test_build_filter_query_with_multiple_filters(self):
        """Test filter query with multiple filters"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query(
            filters={
                "file_type": ".pdf",
                "min_token_count": 100
            },
            user_access=["allowed.txt"]
        )

        filter_clauses = query["bool"]["filter"]
        assert len(filter_clauses) == 3

    def test_fuse_rrf(self):
        """Test RRF fusion"""
        from rag_api.elastic_search import fuse_rrf

        es_results = [
            {"filename": "doc1.txt", "chunk_index": 0, "_score": 0.9}
        ]
        chroma_results = [
            {"filename": "doc2.txt", "chunk_index": 0, "relevance_score": 0.8}
        ]

        combined = fuse_rrf(es_results, chroma_results, k=60)

        assert len(combined) == 2
        assert all("combined_score" in r for r in combined)
        assert all("rrf_score" in r for r in combined)

    def test_fuse_weighted(self):
        """Test weighted fusion"""
        from rag_api.elastic_search import fuse_weighted

        es_results = [
            {"filename": "doc1.txt", "chunk_index": 0, "_score": 0.8}
        ]
        chroma_results = [
            {"filename": "doc2.txt", "chunk_index": 0, "relevance_score": 0.9}
        ]

        combined = fuse_weighted(es_results, chroma_results, 0.5, 0.5)

        assert len(combined) == 2
        assert all("combined_score" in r for r in combined)


class TestElasticIndexer:
    """Tests for elastic_indexer.py"""

    def test_generate_doc_id(self):
        """Test document ID generation"""
        from rag_api.elastic_indexer import generate_doc_id

        doc_id = generate_doc_id(123, 5)
        assert doc_id == "123_5"

    def test_generate_doc_id_different_chunks(self):
        """Test different chunk indices generate different IDs"""
        from rag_api.elastic_indexer import generate_doc_id

        id1 = generate_doc_id(100, 0)
        id2 = generate_doc_id(100, 1)
        id3 = generate_doc_id(100, 2)

        assert id1 != id2 != id3

    def test_create_document_from_chunk(self):
        """Test document creation from chunk"""
        from rag_api.elastic_indexer import create_document_from_chunk

        chunk_data = {
            "page_content": "Test content",
            "metadata": {
                "filename": "test.txt",
                "file_type": ".txt",
                "chunk_index": 0,
                "token_count": 100,
                "created_at": 1234567890.0,
                "modified_at": 1234567890.0
            }
        }

        doc = create_document_from_chunk(chunk_data, doc_id=1)

        assert doc["doc_id"] == 1
        assert doc["filename"] == "test.txt"
        assert doc["content"] == "Test content"
        assert doc["content_normalized"] is not None
        assert doc["file_type"] == ".txt"
        assert doc["chunk_index"] == 0
        assert doc["token_count"] == 100


class TestElasticAPI:
    """Tests for elastic_api.py"""

    def test_essearch_request_model(self):
        """Test ESSearchRequest model"""
        from rag_api.elastic_api import ESSearchRequest

        request = ESSearchRequest(query="test query")
        assert request.query == "test query"
        assert request.index == "documents"
        assert request.size == 10
        assert request.highlight is True

    def test_hybrid_search_request_model(self):
        """Test HybridSearchRequest model"""
        from rag_api.elastic_api import HybridSearchRequest

        request = HybridSearchRequest(query="test")
        assert request.query == "test"
        assert request.semantic_weight == 0.6
        assert request.keyword_weight == 0.4
        assert request.fusion_method == "rrf"

    def test_api_response_model(self):
        """Test APIResponse model"""
        from rag_api.elastic_api import APIResponse

        response = APIResponse(
            status="success",
            message="Test message",
            data={"key": "value"}
        )
        assert response.status == "success"
        assert response.data["key"] == "value"


class TestSearchFunctionality:
    """Integration tests for search functionality"""

    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        return [
            {
                "doc_id": 1,
                "filename": "document1.txt",
                "content": "This is a test document about machine learning",
                "content_normalized": "test document machine learning",
                "file_type": ".txt",
                "chunk_index": 0,
                "token_count": 10,
                "embedding": [0.1] * 384,
                "relevance_score": 0.0
            },
            {
                "doc_id": 2,
                "filename": "document2.txt",
                "content": "Another document about deep learning and neural networks",
                "content_normalized": "document deep learning neural networks",
                "file_type": ".txt",
                "chunk_index": 0,
                "token_count": 12,
                "embedding": [0.2] * 384,
                "relevance_score": 0.0
            }
        ]

    def test_preprocessing_russian_text(self):
        """Test text preprocessing for Russian"""
        from chroma_utils import preprocess_text

        text = "Привет мир! Это тест."
        result = preprocess_text(text, language='russian')

        assert isinstance(result, str)
        assert len(result) > 0

    def test_preprocessing_removes_urls(self):
        """Test that URLs are removed"""
        from chroma_utils import preprocess_text

        text = "Visit https://example.com for more info"
        result = preprocess_text(text)

        assert "https://example.com" not in result
        assert "http" not in result

    def test_preprocessing_normalizes_whitespace(self):
        """Test whitespace normalization"""
        from chroma_utils import preprocess_text

        text = "This   is  a    test   with   spaces"
        result = preprocess_text(text)

        assert "  " not in result


class TestFuzzyMatching:
    """Tests for fuzzy matching functionality"""

    def test_fuzzy_query_structure(self):
        """Test that fuzzy queries have correct structure"""
        from rag_api.elastic_search import build_fulltext_query

        query = build_fulltext_query("test", fuzziness="AUTO")

        multi_match = query["bool"]["should"][0]["multi_match"]
        assert multi_match["prefix_length"] == 2
        assert "fuzziness" in multi_match


class TestSecurityFiltering:
    """Tests for security-aware filtering"""

    def test_access_filter_for_admin(self):
        """Test that admin has access to all files"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query(user_access=None)
        assert query["bool"]["filter"] == []

    def test_access_filter_for_user(self):
        """Test that user has restricted access"""
        from rag_api.elastic_search import build_filter_query

        query = build_filter_query(user_access=["file1.txt", "file2.txt"])

        filter_clauses = query["bool"]["filter"]
        assert len(filter_clauses) == 1
        assert filter_clauses[0]["terms"]["filename"] == ["file1.txt", "file2.txt"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
